module.exports = {
  apps: [
    {
      name: "backend",
      cwd: "./backend",
      script: "poetry run uvicorn main:app --reload --loop asyncio",
      env: {
        KEYBASE_COMMAND: "docker exec -u keybase keybase keybase"
      }
    },
    {
      name: "frontend",
      cwd: "./frontend",
      script: "npm run dev",
    },
  ],
};
