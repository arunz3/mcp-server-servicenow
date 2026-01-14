import asyncio
import json
import logging
from mcp.server.stdio import stdio_server
import mcp.types as types

# Import from our modular server setup
from server import server, sn_client, model, logger

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls for ServiceNow operations."""
    try:
        if name == "create_incident":
            result = await sn_client.create_record("incident", arguments)
            return [types.TextContent(type="text", text=f"Incident created successfully: {result.get('number')} (sys_id: {result.get('sys_id')})")]

        elif name == "create_kb_article":
            data = {
                "short_description": arguments.get("short_description"),
                "text": arguments.get("article_body"),
                "workflow_state": arguments.get("workflow_state", "draft"),
                "kb_knowledge_base": arguments.get("kb_knowledge_base")
            }
            result = await sn_client.create_record("kb_knowledge", data)
            return [types.TextContent(type="text", text=f"KB Article created successfully: {result.get('number')} (sys_id: {result.get('sys_id')})")]

        elif name == "create_client_script":
            data = {
                "name": arguments.get("name"),
                "table": arguments.get("table"),
                "script": arguments.get("script"),
                "type": arguments.get("script_type"),
                "field": arguments.get("field_name"),
                "active": arguments.get("active", True)
            }
            result = await sn_client.create_record("sys_script_client", data)
            return [types.TextContent(type="text", text=f"Client Script created: {result.get('name')} (sys_id: {result.get('sys_id')})")]

        elif name == "create_business_rule":
            data = {
                "name": arguments.get("name"),
                "collection": arguments.get("table"),
                "script": arguments.get("script"),
                "when_toggle": arguments.get("when"),
                "action_insert": arguments.get("action_insert", True),
                "action_update": arguments.get("action_update", False),
                "action_delete": arguments.get("action_delete", False),
                "action_query": arguments.get("action_query", False),
                "active": arguments.get("active", True)
            }
            result = await sn_client.create_record("sys_script", data)
            return [types.TextContent(type="text", text=f"Business Rule created: {result.get('name')} (sys_id: {result.get('sys_id')})")]

        elif name == "create_sla_definition":
            data = {
                "name": arguments.get("name"),
                "collection": arguments.get("table"),
                "duration": f"PT{arguments.get('duration_seconds')}S",
                "start_condition": arguments.get("start_condition"),
                "stop_condition": arguments.get("stop_condition"),
                "pause_condition": arguments.get("pause_condition")
            }
            result = await sn_client.create_record("contract_sla", data)
            return [types.TextContent(type="text", text=f"SLA Definition created: {result.get('name')} (sys_id: {result.get('sys_id')})")]

        elif name == "create_record_producer":
            producer_data = {
                "name": arguments.get("name"),
                "table_name": arguments.get("table_name"),
                "short_description": arguments.get("short_description"),
                "category": arguments.get("category_sys_id"),
                "script": arguments.get("script")
            }
            producer = await sn_client.create_record("sc_cat_item_producer", producer_data)
            producer_id = producer.get("sys_id")
            
            created_vars = []
            for var in arguments.get("variables", []):
                var_data = {
                    "cat_item": producer_id,
                    "name": var.get("name"),
                    "question_text": var.get("label"),
                    "type": 6 if var.get("type") == "string" else 1 if var.get("type") == "choice" else 2,
                    "mandatory": var.get("mandatory", False)
                }
                v_res = await sn_client.create_record("item_option_new", var_data)
                created_vars.append(v_res.get("name"))

            return [types.TextContent(type="text", text=f"Record Producer created: {producer.get('name')} (sys_id: {producer_id}) with variables: {', '.join(created_vars)}")]

        elif name == "create_variable_set":
            set_data = {
                "name": arguments.get("name"),
                "description": arguments.get("description")
            }
            vset = await sn_client.create_record("item_option_new_set", set_data)
            set_id = vset.get("sys_id")
            
            for var in arguments.get("variables", []):
                var_data = {
                    "variable_set": set_id,
                    "name": var.get("name"),
                    "question_text": var.get("label"),
                    "mandatory": var.get("mandatory", False)
                }
                await sn_client.create_record("item_option_new", var_data)

            return [types.TextContent(type="text", text=f"Variable Set created: {vset.get('name')} (sys_id: {set_id})")]

        elif name == "get_incident":
            number = arguments.get("number")
            sys_id = arguments.get("sys_id")
            
            if sys_id:
                result = await sn_client.get_record("incident", sys_id)
            else:
                # Query by number
                query = f"number={number}"
                results = await sn_client.list_records("incident", {"sysparm_query": query, "sysparm_limit": 1})
                if not results:
                    return [types.TextContent(type="text", text=f"Incident {number} not found.")]
                result = results[0]
            
            if not isinstance(result, dict):
                return [types.TextContent(type="text", text=f"Error: Unexpected response format from ServiceNow for incident {number or sys_id}. Got: {str(result)}")]
                
            details = [
                f"Number: {result.get('number', 'N/A')}",
                f"State: {result.get('incident_state', result.get('state', 'N/A'))}",
                f"Priority: {result.get('priority', 'N/A')}",
                f"Short Description: {result.get('short_description', 'N/A')}",
                f"Assignment Group: {result.get('assignment_group', {}).get('display_value', 'Unassigned') if isinstance(result.get('assignment_group'), dict) else 'Unassigned'}",
                f"Assigned To: {result.get('assigned_to', {}).get('display_value', 'Unassigned') if isinstance(result.get('assigned_to'), dict) else 'Unassigned'}",
                f"Updated: {result.get('sys_updated_on', 'N/A')}"
            ]
            return [types.TextContent(type="text", text="\n".join(details))]

        elif name == "update_incident":
            number = arguments.get("number")
            # Find the sys_id first
            query = f"number={number}"
            results = await sn_client.list_records("incident", {"sysparm_query": query, "sysparm_limit": 1})
            if not results:
                return [types.TextContent(type="text", text=f"Incident {number} not found.")]
            
            sys_id = results[0].get("sys_id")
            # Prepare update data (remove number from arguments)
            update_data = {k: v for k, v in arguments.items() if k != "number"}
            result = await sn_client.update_record("incident", sys_id, update_data)
            
            return [types.TextContent(type="text", text=f"Incident {number} updated successfully.")]

        elif name == "list_incidents":
            limit = arguments.get("limit", 10)
            priority = arguments.get("priority")
            state = arguments.get("state")
            
            query_parts = []
            if priority: query_parts.append(f"priority={priority}")
            if state: query_parts.append(f"state={state}")
            
            query = "^".join(query_parts) if query_parts else "ORDERBYDESCsys_created_on"
            results = await sn_client.list_records("incident", {"sysparm_query": query, "sysparm_limit": limit})
            
            output = [f"Found {len(results)} recent incidents:"]
            for r in results:
                output.append(f"- {r.get('number')}: {r.get('short_description')} (State: {r.get('state')}, Priority: {r.get('priority')})")
            
            return [types.TextContent(type="text", text="\n".join(output))]

        elif name == "smart_incident":
            if not model:
                return [types.TextContent(type="text", text="Gemini AI is not configured. Please set GEMINI_API_KEY.")]
            
            prompt = f"""
            Analyze the following issue report and extract structured details for a ServiceNow incident.
            Output ONLY a JSON object with: short_description, description, urgency (1, 2, or 3), impact (1, 2, or 3).
            
            Report: {arguments.get('unstructured_text')}
            
            Default to urgency 3 and impact 3 if not clear.
            JSON:
            """
            response = model.generate_content(prompt)
            try:
                text = response.text.strip()
                if '```json' in text:
                    text = text.split('```json')[1].split('```')[0].strip()
                elif '```' in text:
                    text = text.split('```')[1].split('```')[0].strip()
                
                structured_data = json.loads(text)
                result = await sn_client.create_record("incident", structured_data)
                return [types.TextContent(type="text", text=f"Smart Incident created: {result.get('number')}\nExtracted Data: {json.dumps(structured_data, indent=2)}")]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Failed to parse AI response: {str(e)}\nRaw Response: {response.text}")]

        elif name == "smart_kb_generator":
            if not model:
                return [types.TextContent(type="text", text="Gemini AI is not configured. Please set GEMINI_API_KEY.")]
            
            prompt = f"""
            Convert the following content into a professional ServiceNow Knowledge Base article.
            Format the output in HTML. Include a clear title and structured body (h1, p, ul/li).
            
            Target Audience: {arguments.get('target_audience', 'General Users')}
            Source: {arguments.get('source_content')}
            
            Output ONLY the HTML body content.
            """
            response = model.generate_content(prompt)
            kb_body = response.text.strip()
            title_prompt = f"Generate a short, concise title (max 60 chars) for this KB article content: {kb_body[:500]}"
            title_response = model.generate_content(title_prompt)
            
            data = {
                "short_description": title_response.text.strip().replace('"', ''),
                "text": kb_body,
                "workflow_state": "draft"
            }
            result = await sn_client.create_record("kb_knowledge", data)
            return [types.TextContent(type="text", text=f"Smart KB Article created as Draft: {result.get('number')}\nTitle: {data['short_description']}")]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
