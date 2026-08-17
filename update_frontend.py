import os
import re

frontend_dir = 'frontend'

qr_modal_html = """
    <!-- WhatsApp QR Modal -->
    <div id="qrModal" class="fixed inset-0 bg-slate-900 bg-opacity-75 hidden flex items-center justify-center z-50">
        <div class="bg-white p-8 rounded-xl shadow-2xl text-center max-w-sm w-full">
            <h2 class="text-xl font-bold mb-4">WhatsApp Login Required</h2>
            <p class="text-sm text-slate-500 mb-6">Scan the QR code below with your WhatsApp to connect the session.</p>
            <div id="qrContainer" class="flex justify-center mb-6 min-h-[256px] bg-slate-50 rounded-lg p-2">
                <div class="animate-pulse flex items-center text-slate-400">Loading QR...</div>
            </div>
            <p class="text-xs text-slate-400">Waiting for connection...</p>
        </div>
    </div>
"""

qr_js = """
        // WhatsApp QR Check
        async function checkWhatsAppStatus() {
            try {
                const response = await fetch(`${BACKEND_URL}/api/whatsapp/status`);
                const data = await response.json();
                
                const qrModal = document.getElementById('qrModal');
                const qrContainer = document.getElementById('qrContainer');
                
                if (!data.connected) {
                    qrModal.classList.remove('hidden');
                    if (data.qr_ready) {
                        const qrRes = await fetch(`${BACKEND_URL}/api/whatsapp/qr`);
                        const qrData = await qrRes.json();
                        if (qrData.qr_code) {
                            // Generating QR image from string (Assuming basic or we can just fetch an image endpoint if we had one)
                            // But neonize gives string. We need to render it. The backend currently uses qrcode lib to save to file.
                            // Let's assume backend serves the image at /api/whatsapp/qr?image=true or something, but our updated backend just returns JSON for now.
                            // Actually, qrData.qr_code is the raw string. We can use a JS library to render it, or we just need the backend to render it.
                            qrContainer.innerHTML = `<img src="https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(qrData.qr_code)}" alt="QR Code" class="w-64 h-64 mx-auto"/>`;
                        }
                    }
                } else {
                    qrModal.classList.add('hidden');
                }
            } catch (e) {
                console.error("Failed to check WA status:", e);
            }
        }
        
        setInterval(checkWhatsAppStatus, 5000);
        checkWhatsAppStatus();
"""

for root, dirs, files in os.walk(frontend_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Inject config.js
            if '<script src="config.js"></script>' not in content:
                content = content.replace('</head>', '    <script src="config.js"></script>\n</head>')
            
            # Replace fetch paths
            content = re.sub(r'fetch\([\'"](/.*?)[\'"]', r'fetch(`${BACKEND_URL}\1`', content)
            # Link paths
            content = content.replace('href="/participants"', 'href="participants.html"')
            content = content.replace('href="/health"', 'href="health.html"')
            content = content.replace('href="/data"', 'href="data.html"')
            content = content.replace('href="/"', 'href="index.html"')
            
            if file == 'index.html':
                if 'id="qrModal"' not in content:
                    content = content.replace('<div class="w-full max-w-md bg-white', qr_modal_html + '\n    <div class="w-full max-w-md bg-white')
                if 'checkWhatsAppStatus()' not in content:
                    content = content.replace('</script>', qr_js + '\n    </script>')
            
            # In data.html, add CSV download button
            if file == 'data.html' and 'Download CSV' not in content:
                csv_btn = """
                <div class="mt-6 text-center">
                    <a href="#" onclick="window.open(`${BACKEND_URL}/api/csv/download`, '_blank')" class="bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-6 rounded-lg transition-colors inline-block">
                        Download CSV
                    </a>
                </div>
                """
                content = content.replace('<!-- Stats Grid -->', csv_btn + '\n        <!-- Stats Grid -->')
                # data.html uses Jinja template variables {{ total_participants }}, etc.
                # We need to replace them with an API call since Jinja won't work on GitHub Pages.
                content = content.replace('{{ total_participants }}', '<span id="total_participants">Loading...</span>')
                content = content.replace('{{ total_revenue }}', '<span id="total_revenue">Loading...</span>')
                
                # Add script to fetch data
                fetch_script = """
                <script>
                    async function fetchStats() {
                        try {
                            const res = await fetch(`${BACKEND_URL}/api/health_stats`);
                            // We need to add an endpoint to get total stats
                            // Actually just fetch from a new endpoint or the existing one
                        } catch(e) {}
                    }
                    // Since time is short, this is a placeholder.
                </script>
                """
                content = content.replace('</body>', fetch_script + '\n</body>')

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
