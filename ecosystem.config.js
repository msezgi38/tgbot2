module.exports = {
    apps: [
        {
            name: "tgbot3-webhook",
            script: "webhook_server.py",
            cwd: "/opt/tgbot3/dialer",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
        {
            name: "tgbot3-worker",
            script: "campaign_worker.py",
            cwd: "/opt/tgbot3/dialer",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
        {
            name: "tgbot3-bot",
            script: "main.py",
            cwd: "/opt/tgbot3/bot",
            interpreter: "python3",
            autorestart: true,
            watch: false,
            max_restarts: 10,
            restart_delay: 5000,
        },
    ],
};
