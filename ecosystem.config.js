module.exports = {
    apps: [
        {
            name: "tgbot5-webhook",
            script: "webhook_server.py",
            cwd: "/opt/tgbot5/dialer",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
        {
            name: "tgbot5-worker",
            script: "campaign_worker.py",
            cwd: "/opt/tgbot5/dialer",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
        {
            name: "tgbot5-bot",
            script: "main.py",
            cwd: "/opt/tgbot5/bot",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
    ],
};
