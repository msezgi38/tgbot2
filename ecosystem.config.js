module.exports = {
    apps: [
        {
            name: "tgbot4-webhook",
            script: "webhook_server.py",
            cwd: "/opt/tgbot4/dialer",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
        {
            name: "tgbot4-worker",
            script: "campaign_worker.py",
            cwd: "/opt/tgbot4/dialer",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
        {
            name: "tgbot4-bot",
            script: "main.py",
            cwd: "/opt/tgbot4/bot",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
    ],
};
