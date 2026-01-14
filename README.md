# ServiceNow MCP Server with Gemini AI

A powerful Model Context Protocol (MCP) server that connects Claude Desktop directly to your ServiceNow instance. It includes standard tools for record management and AI-powered "Smart" tools using Gemini 1.5 Flash.

## 🚀 Features

- **Incident Management**: Create and track incidents.
- **Service Catalog**: Create Record Producers, Variable Sets, and Variables.
- **Workflow Tools**: Automate creation of Client Scripts, Business Rules, and SLA Definitions.
- **Gemini AI Integration**:
  - `smart_incident`: Automatically extracts ticket details from messy logs or chat transcripts.
  - `smart_kb_generator`: Turns rough notes into professional HTML Knowledge Base articles.

## 🛠️ Setup

### 1. Prerequisites
- Python 3.12+
- A ServiceNow Developer Instance
- A Google Gemini API Key

### 2. Installation
Clone the repository and install dependencies:
```bash
pip install -e .
```

### 3. Environment Configuration
Create a `.env` file in the root directory:
```env
SERVICENOW_INSTANCE=https://devXXXXX.service-now.com
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=your_password
GEMINI_API_KEY=your_gemini_api_key
```

## 🤖 Claude Desktop Configuration

To use this with Claude Desktop, add the following to your `claude_desktop_config.json` (typically found in `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "servicenow": {
      "command": "python",
      "args": [
        "-u",
        "C:/Arun/Projects/mcp-server-servicenow/main.py"
      ]
    }
  }
}
```
*Note: Ensure the path to `main.py` is absolute and uses forward slashes `/`.*

## 📖 Usage Examples

### Manual Incident
> "Create a high priority incident for the production database being unreachable."

### AI-Powered (Smart) Incident
> "Based on this chat log [Copy/Paste Log], create a smart incident in ServiceNow."

### Knowledge Base Generation
> "Turn these bullet points into a KB article for end users: [Your Notes]"

## 📂 Project Structure
- `server.py`: Core configuration and ServiceNow API client.
- `main.py`: Tool implementations and MCP server entry point.
