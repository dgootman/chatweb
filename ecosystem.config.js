module.exports = {
  apps: [
    {
      name: "backend",
      cwd: "./backend",
      script: "poetry run uvicorn main:app --reload --loop asyncio",
    },
    {
      name: "frontend",
      cwd: "./frontend",
      script: "npm run dev",
    },
  ],
};
