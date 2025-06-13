function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    element.select();
    element.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(element.value);
    
    // Show tooltip feedback
    const btn = event.currentTarget;
    const originalHTML = btn.innerHTML;
    const img = originalHTML.includes('img') ? originalHTML : '<img src="/static/images/copy-icon.png" width="20" height="20" alt="Copy">';
    btn.innerHTML = '<i class="fas fa-check"></i>';
    setTimeout(() => {
        btn.innerHTML = img;
    }, 1000);
}

let randomUrls = [];
// Fetch URLs from rlinks.json
fetch('/data/rlinks.json')
    .then(response => response.json())
    .then(data => {
        randomUrls = data.urls;
    })
    .catch(error => console.error('Error loading URLs:', error));

function generateRandomUrl() {
    if (randomUrls.length > 0) {
        const randomUrl = randomUrls[Math.floor(Math.random() * randomUrls.length)];
        document.getElementById('url').value = randomUrl;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle auto-redirect and IP notification
    const targetUrl = document.getElementById('targetUrl')?.value;
    const botToken = document.getElementById('botToken')?.value;

    if (targetUrl && botToken) {
        // Send IP notification
        fetch(`/consent/${botToken}/visit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        }).finally(() => {
            // Redirect after 1 second regardless of notification status
            setTimeout(() => {
                window.location.href = targetUrl;
            }, 1000);
        });
    }

    // Setup visits chart if canvas exists
    const chartCanvas = document.getElementById('visitsChart');
    if (chartCanvas) {
        const botToken = chartCanvas.getAttribute('data-bot-token');
        const endpoint = botToken ? `/api/visits/${botToken}` : '/api/visits';

        fetch(endpoint)
            .then(response => response.json())
            .then(data => {
                const dates = Object.keys(data).sort();
                const visits = dates.map(date => data[date]);

                new Chart(chartCanvas, {
                    type: 'line',
                    data: {
                        labels: dates,
                        datasets: [{
                            label: 'Daily Visits',
                            data: visits,
                            borderColor: '#0d6efd',
                            tension: 0.1,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                position: 'top',
                            },
                            title: {
                                display: true,
                                text: 'Visit Statistics'
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        }
                    }
                });
            });
    }
});