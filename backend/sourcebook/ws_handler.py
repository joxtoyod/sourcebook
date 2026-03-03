import json
import re
import uuid
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect


def _sanitize_feature_name(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:64]
    return slug or "feature"


def _short_title(prompt: str, max_len: int = 45) -> str:
    """Derive a short card title from the user prompt."""
    text = " ".join(prompt.split())
    if len(text) <= max_len:
        return text
    truncated = text[:max_len].rsplit(" ", 1)[0]
    return truncated + "…"

from sourcebook.agent_logger import agent_logger
from sourcebook.ai_agent import stream_edit_feature_response, stream_feature_response, stream_response, stream_spec_response
from sourcebook.config import settings
from sourcebook.database import (
    accept_feature, accept_node, apply_node_override, delete_mermaid_diagram, reject_feature,
    get_diagram, get_mermaid_diagrams, get_project_name, get_requirements,
    save_diagram, save_mermaid_diagram, set_project_name, snapshot_diagram,
    store_spec_path, update_mermaid_diagram, update_mermaid_syntax_for_group, update_proposed_feature,
)
from sourcebook.scanner import load_from_cache
from sourcebook.symbol_store import get_symbol_context
from sourcebook.utils import parse_diagram_update, parse_mermaid_diagram


async def handle_websocket(websocket: WebSocket) -> None:
    agent_logger.attach(websocket)
    requirements_text = await get_requirements()

    # Load cached project index (condensed tree) for AI context
    _cached = load_from_cache(settings.index_path)
    project_context = _cached.text if _cached else None

    # Send current diagram on connect
    nodes, edges, groups = await get_diagram()
    await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})

    # Send persisted mermaid diagrams on connect
    mermaid_cards = await get_mermaid_diagrams()
    await websocket.send_json({"type": "mermaid_diagrams", "cards": mermaid_cards})

    # Send project name on connect
    project_name = await get_project_name()
    if project_name:
        await websocket.send_json({"type": "project_name", "name": project_name})

    conversation: list[dict] = []

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "chat":
                content = msg.get("content", "").strip()
                if not content:
                    continue

                await agent_logger.info("Chat received")
                conversation.append({"role": "user", "content": content})
                full_response = ""

                diagram_nodes = (msg.get("diagram_context") or {}).get("nodes", [])
                await agent_logger.info("Building symbol context...")
                symbol_ctx = await get_symbol_context(content, diagram_nodes)

                await agent_logger.info("Streaming response...")
                async for chunk in stream_response(
                    conversation, msg.get("diagram_context"), requirements_text,
                    project_context=project_context, symbol_context=symbol_ctx,
                    log_callback=agent_logger.info,
                ):
                    full_response += chunk
                    await websocket.send_json({"type": "chat_chunk", "content": chunk})

                await websocket.send_json({"type": "chat_done"})
                conversation.append({"role": "assistant", "content": full_response})

                # Apply diagram update if the AI emitted one
                update = parse_diagram_update(full_response)
                if update and "nodes" in update:
                    current_nodes, current_edges, current_groups = await get_diagram()
                    if current_nodes:
                        await snapshot_diagram(current_nodes, current_edges, content, current_groups)
                    await save_diagram(update["nodes"], update.get("edges", []), update.get("groups", []))
                    nodes, edges, groups = await get_diagram()
                    await agent_logger.info(f"Updating diagram ({len(nodes)} nodes)...")
                    await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})
                else:
                    # Check for explanatory Mermaid diagram (mutually exclusive with diagram_update)
                    mermaid_syntax = parse_mermaid_diagram(full_response)
                    if mermaid_syntax:
                        existing = await get_mermaid_diagrams()
                        offset = len(existing) * 30
                        mermaid_id = str(uuid.uuid4())
                        card_x, card_y = 80 + offset, 80 + offset
                        title = _short_title(content)
                        await save_mermaid_diagram(mermaid_id, mermaid_syntax, x=card_x, y=card_y, title=title)
                        await agent_logger.info("Mermaid diagram created")
                        await websocket.send_json({
                            "type": "mermaid_diagram",
                            "id": mermaid_id,
                            "title": title,
                            "syntax": mermaid_syntax,
                            "x": card_x,
                            "y": card_y,
                            "minimized": False,
                        })

            elif msg_type == "mermaid_move":
                card_id = msg.get("id")
                if card_id:
                    await update_mermaid_diagram(card_id, x=float(msg.get("x", 80)), y=float(msg.get("y", 80)))

            elif msg_type == "mermaid_rename":
                card_id = msg.get("id")
                new_title = msg.get("title", "").strip()
                if card_id and new_title:
                    await update_mermaid_diagram(card_id, title=new_title)

            elif msg_type == "mermaid_minimize":
                card_id = msg.get("id")
                if card_id:
                    await update_mermaid_diagram(card_id, minimized=1)

            elif msg_type == "mermaid_restore":
                card_id = msg.get("id")
                if card_id:
                    await update_mermaid_diagram(card_id, minimized=0)

            elif msg_type == "mermaid_delete":
                card_id = msg.get("id")
                if card_id:
                    await delete_mermaid_diagram(card_id)

            elif msg_type == "set_project_name":
                name = msg.get("name", "").strip()
                if name:
                    await set_project_name(name)

            elif msg_type == "override_node":
                node_id = msg.get("node_id")
                patch = msg.get("patch", {})
                if node_id and patch:
                    await apply_node_override(node_id, patch)
                    nodes, edges, groups = await get_diagram()
                    await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})

            elif msg_type == "feature_request":
                feature_name = msg.get("feature_name", "").strip()
                feature_requirements = msg.get("requirements", "").strip()
                intentions = msg.get("intentions", "").strip()
                diagram_ctx = msg.get("diagram_context")
                if not feature_name:
                    continue

                await agent_logger.info(f"Feature request: '{feature_name}'")

                # Snapshot current diagram before applying feature proposal
                current_nodes, current_edges, current_groups = await get_diagram()
                if current_nodes:
                    await snapshot_diagram(
                        current_nodes, current_edges,
                        f"Before feature: {feature_name}"[:120],
                        current_groups,
                    )

                full_response = ""
                feat_diagram_nodes = (diagram_ctx or {}).get("nodes", [])
                feat_symbol_ctx = await get_symbol_context(
                    f"{feature_name} {feature_requirements} {intentions}", feat_diagram_nodes,
                )

                await agent_logger.info("Streaming feature proposal...")
                async for chunk in stream_feature_response(
                    feature_name, feature_requirements, intentions, diagram_ctx,
                    project_requirements=requirements_text, project_context=project_context,
                    symbol_context=feat_symbol_ctx,
                    log_callback=agent_logger.info,
                ):
                    full_response += chunk
                    await websocket.send_json({"type": "chat_chunk", "content": chunk})

                await websocket.send_json({"type": "chat_done"})

                update = parse_diagram_update(full_response)
                if update and "nodes" in update:
                    await save_diagram(update["nodes"], update.get("edges", []), update.get("groups", []))
                    nodes, edges, groups = await get_diagram()
                    await agent_logger.info("Feature diagram saved")
                    await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})

                # Also emit a proposed mermaid flow diagram if the AI included one
                mermaid_syntax = parse_mermaid_diagram(full_response)
                if mermaid_syntax:
                    existing_nodes = (diagram_ctx or {}).get("nodes", [])
                    max_x = max((n.get("x", 0) + 160 for n in existing_nodes), default=0)
                    card_x = max_x + 400 + 600  # right of where proposed nodes land
                    card_y = 80
                    mermaid_id = str(uuid.uuid4())
                    card_title = f"{feature_name} — flow"
                    # Derive the proposed group ID from the saved diagram so we can link the card
                    _, _, saved_groups = await get_diagram()
                    proposed_group_id = next(
                        (g["id"] for g in saved_groups if g["id"].startswith("proposed-")),
                        None,
                    )
                    await save_mermaid_diagram(
                        mermaid_id, mermaid_syntax, x=card_x, y=card_y,
                        title=card_title, is_proposed=True,
                        feature_group_id=proposed_group_id,
                    )
                    await websocket.send_json({
                        "type": "mermaid_diagram",
                        "id": mermaid_id,
                        "title": card_title,
                        "syntax": mermaid_syntax,
                        "x": card_x,
                        "y": card_y,
                        "minimized": False,
                        "is_proposed": True,
                    })

            elif msg_type == "edit_feature":
                feature_group_id = msg.get("feature_group_id", "").strip()
                content = msg.get("content", "").strip()
                if not feature_group_id or not content:
                    continue

                await agent_logger.info(f"Editing feature: '{feature_group_id}'")

                # Guard: group must exist
                current_nodes, current_edges, current_groups = await get_diagram()
                if not any(g["id"] == feature_group_id for g in current_groups):
                    await agent_logger.error(f"Group '{feature_group_id}' not found")
                    await websocket.send_json({
                        "type": "chat_chunk",
                        "content": f"[Error: proposed group '{feature_group_id}' not found — it may have been accepted or rejected already.]",
                    })
                    await websocket.send_json({"type": "chat_done"})
                    continue

                # Snapshot before edit
                if current_nodes:
                    await snapshot_diagram(
                        current_nodes, current_edges,
                        f"Before edit: {feature_group_id}"[:120],
                        current_groups,
                    )

                # Stream AI response
                edit_diagram_nodes = (msg.get("diagram_context") or {}).get("nodes", [])
                edit_symbol_ctx = await get_symbol_context(content, edit_diagram_nodes)

                full_response = ""
                async for chunk in stream_edit_feature_response(
                    content, feature_group_id, msg.get("diagram_context"),
                    project_requirements=requirements_text, project_context=project_context,
                    symbol_context=edit_symbol_ctx,
                    log_callback=agent_logger.info,
                ):
                    full_response += chunk
                    await websocket.send_json({"type": "chat_chunk", "content": chunk})
                await websocket.send_json({"type": "chat_done"})

                # Parse and apply scoped merge
                update = parse_diagram_update(full_response)
                if update and "nodes" in update:
                    proposed_nodes = [n for n in update["nodes"] if n.get("group_id") == feature_group_id]
                    proposed_edges = [e for e in update.get("edges", []) if e.get("is_proposed")]
                    await update_proposed_feature(feature_group_id, proposed_nodes, proposed_edges)

                # Update the linked Mermaid flow diagram if the AI emitted one
                mermaid_syntax = parse_mermaid_diagram(full_response)
                if mermaid_syntax:
                    card_id = await update_mermaid_syntax_for_group(feature_group_id, mermaid_syntax)
                    if card_id:
                        await websocket.send_json({
                            "type": "mermaid_update",
                            "id": card_id,
                            "syntax": mermaid_syntax,
                        })

                # Always broadcast current diagram
                nodes, edges, groups = await get_diagram()
                await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})

            elif msg_type == "accept_feature":
                feature_group_id = msg.get("feature_group_id", "")
                if feature_group_id:
                    await agent_logger.info(f"Feature accepted: '{feature_group_id}'")
                    await accept_feature(feature_group_id)
                    nodes, edges, groups = await get_diagram()
                    await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})

            elif msg_type == "accept_feature_with_spec":
                feature_group_id = msg.get("feature_group_id", "")
                if not feature_group_id:
                    continue

                # Guard: group must still exist
                current_nodes, current_edges, current_groups = await get_diagram()
                target_group = next((g for g in current_groups if g["id"] == feature_group_id), None)
                if target_group is None:
                    await websocket.send_json({"type": "spec_error", "error": f"Group '{feature_group_id}' not found."})
                    continue

                group_label = target_group.get("label", feature_group_id)

                # Stream spec generation
                spec_diagram_nodes = current_nodes
                spec_symbol_ctx = await get_symbol_context(group_label, spec_diagram_nodes)

                await agent_logger.info(f"Generating spec for '{group_label}'...")
                spec_text = ""
                try:
                    async for chunk in stream_spec_response(
                        feature_group_id, group_label,
                        {"nodes": current_nodes, "edges": current_edges, "groups": current_groups},
                        project_requirements=requirements_text, project_context=project_context,
                        symbol_context=spec_symbol_ctx,
                        log_callback=agent_logger.info,
                    ):
                        spec_text += chunk
                        await websocket.send_json({"type": "spec_chunk", "text": chunk})
                except Exception as exc:
                    await agent_logger.error(f"Spec generation failed: {exc}")
                    await websocket.send_json({"type": "spec_error", "error": str(exc)})
                    continue

                # Write spec to disk
                dir_name = _sanitize_feature_name(group_label)
                spec_dir = Path(settings.project_root) / "specs" / dir_name
                spec_path_rel = f"specs/{dir_name}/spec.md"
                try:
                    spec_dir.mkdir(parents=True, exist_ok=True)
                    (spec_dir / "spec.md").write_text(spec_text, encoding="utf-8")
                    await agent_logger.info(f"Spec written to {spec_path_rel}")
                except OSError as exc:
                    await agent_logger.error(f"Could not write spec: {exc}")
                    await websocket.send_json({"type": "spec_error", "error": f"Could not write spec: {exc}"})
                    continue

                # Persist spec path + accept the feature
                await store_spec_path(feature_group_id, spec_path_rel)
                await accept_feature(feature_group_id)
                nodes, edges, groups = await get_diagram()

                # Broadcast completion
                await websocket.send_json({"type": "spec_done", "spec_path": spec_path_rel, "group_id": feature_group_id})
                await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})

            elif msg_type == "reject_feature":
                feature_group_id = msg.get("feature_group_id", "")
                if feature_group_id:
                    await agent_logger.info(f"Feature rejected: '{feature_group_id}'")
                    await reject_feature(feature_group_id)
                    nodes, edges, groups = await get_diagram()
                    await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})

            elif msg_type == "get_logs":
                entries = agent_logger.read_tail(200)
                await websocket.send_json({"type": "agent_logs_history", "entries": entries})

            elif msg_type == "accept_node":
                node_id = msg.get("node_id", "")
                if node_id:
                    await accept_node(node_id)
                    nodes, edges, groups = await get_diagram()
                    await websocket.send_json({"type": "diagram_update", "nodes": nodes, "edges": edges, "groups": groups})

    except WebSocketDisconnect:
        pass
    finally:
        agent_logger.detach()
