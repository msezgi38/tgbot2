module.exports = {
    apps: [
        {
            name: "tgbot2-webhook",
            script: "webhook_server.py",
            cwd: "/opt/tgbot2/dialer",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
        {
            name: "tgbot2-worker",
            script: "campaign_worker.py",
            cwd: "/opt/tgbot2/dialer",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
        {
            name: "tgbot2-bot",
            script: "main.py",
            cwd: "/opt/tgbot2/bot",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
    ],
};
