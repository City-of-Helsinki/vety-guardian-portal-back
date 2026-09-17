FROM nginx:alpine

RUN cat > /usr/share/nginx/html/index.html <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docker Test Page</title>
    <style>
        body {
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: Arial, sans-serif;
            background: #f4f4f5;
            color: #18181b;
        }

        .card {
            padding: 40px;
            text-align: center;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
        }

        h1 {
            margin-top: 0;
        }

        .status {
            color: #16a34a;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Docker Test Page</h1>
        <p class="status">✓ Container is running</p>
        <p>Hello from Nginx!</p>
    </div>
</body>
</html>
EOF

EXPOSE 80
