# Infrastructure Orchestrator UI

Modern React-based dashboard for AI-powered infrastructure orchestration.

## Features

- **Resource Dashboard**: Real-time view of all infrastructure resources and their status
- **Failure Management**: Introduce failures (Redis, PostgreSQL, or both) and reset resources
- **LLM Chat Interface**: Interactive chat showing LLM analysis, reasoning, and tool execution
- **MCP Tools Panel**: View available MCP tools for each resource type
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Installation

```bash
cd frontend
npm install
```

## Running

```bash
npm start
```

The app will open at `http://localhost:3000`

## Environment Variables

Create a `.env` file in the `frontend` directory:

```
REACT_APP_API_URL=http://localhost:8000
```

## Tech Stack

- React 18
- Axios for API calls
- Lucide React for icons
- Custom CSS with modern design system

## Color Theme

- Primary Background: `#0a0e27` (Dark blue)
- Secondary Background: `#151932` (Darker blue)
- Accent Primary: `#00d9ff` (Cyan)
- Accent Secondary: `#7c3aed` (Purple)
- Success: `#10b981` (Green)
- Warning: `#f59e0b` (Orange)
- Danger: `#ef4444` (Red)

