import os
import logging
import httpx
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from mcp.server import Server
import mcp.types as types
import google.generativeai as genai

# Emergency logging to a file that doesn't rely on the logging module
def emergency_log(msg):
    with open(os.path.join(os.path.dirname(__file__), 'emergency.log'), 'a') as f:
        f.write(f"{datetime.now()}: {msg}\n")

emergency_log("Server.py starting")

# Load environment variables explicitly from the current directory
try:
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        emergency_log(f"Loaded .env from {env_path}")
    else:
        load_dotenv() # Fallback to default search
        emergency_log("Loaded .env from default search or skipped")
except Exception as e:
    emergency_log(f"Error loading .env: {str(e)}")

# Configure logging to go EXCLUSIVELY to stderr
log_file = os.path.join(os.path.dirname(__file__), 'mcp_server.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("mcp-servicenow")

# Environment variables
SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE")
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def check_config():
    missing = []
    if not SERVICENOW_INSTANCE: missing.append("SERVICENOW_INSTANCE")
    if not SERVICENOW_USERNAME: missing.append("SERVICENOW_USERNAME")
    if not SERVICENOW_PASSWORD: missing.append("SERVICENOW_PASSWORD")
    if not GEMINI_API_KEY: missing.append("GEMINI_API_KEY")
    
    if missing:
        logger.warning(f"Missing environment variables: {', '.join(missing)}")
    else:
        logger.info(" All environment variables loaded successfully.")

check_config()

# Initialize Gemini if API key is provided
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

# Initialize MCP Server
server = Server("mcp-servicenow")

# ServiceNow API Client
class ServiceNowClient:
    def __init__(self):
        if not all([SERVICENOW_INSTANCE, SERVICENOW_USERNAME, SERVICENOW_PASSWORD]):
            logger.warning("ServiceNow credentials not fully configured in environment variables")
            self.configured = False
        else:
            self.base_url = f"{SERVICENOW_INSTANCE.rstrip('/')}/api/now"
            self.auth = (SERVICENOW_USERNAME, SERVICENOW_PASSWORD)
            self.headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            self.configured = True

    async def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        if not self.configured:
            raise ValueError("ServiceNow client not configured. Check environment variables.")
            
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/{path}"
            response = await client.request(
                method,
                url,
                auth=self.auth,
                headers=self.headers,
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("result")

    async def create_record(self, table: str, data: Dict) -> Dict:
        return await self._request("POST", f"table/{table}", data)

    async def get_record(self, table: str, sys_id: str) -> Dict:
        return await self._request("GET", f"table/{table}/{sys_id}")

    async def update_record(self, table: str, sys_id: str, data: Dict) -> Dict:
        return await self._request("PATCH", f"table/{table}/{sys_id}", data)

    async def list_records(self, table: str, params: Optional[Dict] = None) -> List[Dict]:
        if not self.configured:
            raise ValueError("ServiceNow client not configured.")
            
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/table/{table}"
            response = await client.get(
                url,
                auth=self.auth,
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("result", [])

sn_client = ServiceNowClient()

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available ServiceNow tools."""
    return [
        types.Tool(
            name="create_incident",
            description="Create a new incident in ServiceNow",
            inputSchema={
                "type": "object",
                "properties": {
                    "short_description": {"type": "string", "description": "Brief summary of the incident"},
                    "description": {"type": "string", "description": "Detailed description of the incident"},
                    "urgency": {"type": "string", "enum": ["1", "2", "3"], "description": "1=High, 2=Medium, 3=Low"},
                    "impact": {"type": "string", "enum": ["1", "2", "3"], "description": "1=High, 2=Medium, 3=Low"},
                    "caller_id": {"type": "string", "description": "User sys_id or username for the caller"}
                },
                "required": ["short_description"]
            }
        ),
        types.Tool(
            name="create_kb_article",
            description="Create a new Knowledge Base article in ServiceNow",
            inputSchema={
                "type": "object",
                "properties": {
                    "short_description": {"type": "string", "description": "Title of the KB article"},
                    "article_body": {"type": "string", "description": "HTML content of the article"},
                    "workflow_state": {"type": "string", "enum": ["draft", "review", "published"], "default": "draft"},
                    "kb_knowledge_base": {"type": "string", "description": "Sys_id of the knowledge base"}
                },
                "required": ["short_description", "article_body"]
            }
        ),
        types.Tool(
            name="create_client_script",
            description="Create a new client-side script in ServiceNow",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the script"},
                    "table": {"type": "string", "description": "Table name (e.g., incident)"},
                    "script": {"type": "string", "description": "JavaScript code"},
                    "script_type": {"type": "string", "enum": ["onLoad", "onChange", "onSubmit", "onCellEdit"]},
                    "field_name": {"type": "string", "description": "Field for onChange script"},
                    "active": {"type": "boolean", "default": True}
                },
                "required": ["name", "table", "script", "script_type"]
            }
        ),
        types.Tool(
            name="create_business_rule",
            description="Create a new business rule in ServiceNow",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the rule"},
                    "table": {"type": "string", "description": "Table name"},
                    "script": {"type": "string", "description": "JavaScript code (server-side)"},
                    "when": {"type": "string", "enum": ["before", "after", "async", "display"]},
                    "action_insert": {"type": "boolean", "default": True},
                    "action_update": {"type": "boolean", "default": False},
                    "action_delete": {"type": "boolean", "default": False},
                    "action_query": {"type": "boolean", "default": False},
                    "active": {"type": "boolean", "default": True}
                },
                "required": ["name", "table", "script", "when"]
            }
        ),
        types.Tool(
            name="create_sla_definition",
            description="Create a new SLA definition in ServiceNow",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the SLA"},
                    "table": {"type": "string", "description": "Table name"},
                    "duration_seconds": {"type": "integer", "description": "SLA duration in seconds"},
                    "start_condition": {"type": "string", "description": "Encoded query for start condition"},
                    "stop_condition": {"type": "string", "description": "Encoded query for stop condition"},
                    "pause_condition": {"type": "string", "description": "Encoded query for pause condition"}
                },
                "required": ["name", "table", "duration_seconds", "start_condition", "stop_condition"]
            }
        ),
        types.Tool(
            name="create_record_producer",
            description="Create a new record producer (Cat Item) in ServiceNow",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Display name"},
                    "table_name": {"type": "string", "description": "Table to create record in"},
                    "short_description": {"type": "string"},
                    "category_sys_id": {"type": "string"},
                    "script": {"type": "string", "description": "Post-submission script"},
                    "variables": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                                "type": {"type": "string", "description": "e.g., choice, integer, string, boolean"},
                                "choices": {"type": "array", "items": {"type": "string"}},
                                "mandatory": {"type": "boolean"}
                            }
                        }
                    }
                },
                "required": ["name", "table_name"]
            }
        ),
        types.Tool(
            name="create_variable_set",
            description="Create a reusable variable set for catalog items",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "variables": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                                "type": {"type": "string"},
                                "mandatory": {"type": "boolean"}
                            }
                        }
                    }
                },
                "required": ["name"]
            }
        ),
        types.Tool(
            name="get_incident",
            description="Retrieve details and status of a specific ServiceNow incident",
            inputSchema={
                "type": "object",
                "properties": {
                    "number": {"type": "string", "description": "Incident number (e.g., INC0000001)"},
                    "sys_id": {"type": "string", "description": "Internal record ID"}
                },
                "oneOf": [
                    {"required": ["number"]},
                    {"required": ["sys_id"]}
                ]
            }
        ),
        types.Tool(
            name="list_incidents",
            description="List recent incidents with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "description": "Number of records to return"},
                    "priority": {"type": "string", "enum": ["1", "2", "3", "4", "5"]},
                    "state": {"type": "string", "description": "1=New, 2=In Progress, 3=On Hold, etc."}
                }
            }
        ),
        types.Tool(
            name="update_incident",
            description="Update fields of an existing ServiceNow incident",
            inputSchema={
                "type": "object",
                "properties": {
                    "number": {"type": "string", "description": "Incident number (e.g., INC0010014)"},
                    "short_description": {"type": "string"},
                    "description": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["1", "2", "3"]},
                    "impact": {"type": "string", "enum": ["1", "2", "3"]},
                    "state": {"type": "string", "description": "State code (e.g., 2 for In Progress)"},
                    "comments": {"type": "string", "description": "Add a comment to the incident"}
                },
                "required": ["number"]
            }
        ),
        types.Tool(
            name="smart_incident",
            description="Use Gemini AI to analyze unstructured text and create a structured ServiceNow incident",
            inputSchema={
                "type": "object",
                "properties": {
                    "unstructured_text": {"type": "string", "description": "The user's report or chat log describing the issue"}
                },
                "required": ["unstructured_text"]
            }
        ),
        types.Tool(
            name="smart_kb_generator",
            description="Use Gemini AI to generate a professional KB article from a description or raw notes",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_content": {"type": "string", "description": "Raw notes, incident description, or instructions to turn into a KB article"},
                    "target_audience": {"type": "string", "description": "e.g., 'End Users', 'IT Staff'"}
                },
                "required": ["source_content"]
            }
        )
    ]
