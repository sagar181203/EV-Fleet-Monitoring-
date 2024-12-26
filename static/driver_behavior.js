// Fetch and display driver behavior data
async function fetchDriverBehavior() {
    const response = await fetch('/api/driver_behavior');
    const data = await response.json();
    updateBehaviorTable(data);
    updateCharts(data);
}

function updateBehaviorTable(data) {
    const tbody = document.getElementById('behaviorTableBody');
    tbody.innerHTML = '';
    
    data.forEach(record => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td style="color: #000;">${record.vehicle_name}</td>
            <td style="color: #000;">${record.timestamp}</td>
            <td style="color: #000;">${record.speed} km/h</td>
            <td style="color: #000;">${record.harsh_braking ? '⚠️ Yes' : 'No'}</td>
            <td style="color: #000;">${record.rapid_acceleration ? '⚠️ Yes' : 'No'}</td>
            <td style="color: #000;">${record.idle_time}</td>
            <td style="color: #000;">${record.score}/100</td>
        `;
        tbody.appendChild(row);
    });
}

function updateCharts(data) {
    // Driver Scores Chart
    const scores = data.map(record => record.score);
    const vehicles = data.map(record => record.vehicle_name);
    
    new Chart(document.getElementById('driverScoresChart'), {
        type: 'bar',
        data: {
            labels: vehicles,
            datasets: [{
                label: 'Driver Score',
                data: scores,
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 2,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        font: {
                            size: 11
                        }
                    }
                },
                x: {
                    ticks: {
                        font: {
                            size: 11
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Driver Performance Scores',
                    font: {
                        size: 14
                    }
                }
            }
        }
    });

    // Behavior Incidents Chart
    const incidents = {
        'Harsh Braking': data.filter(record => record.harsh_braking).length,
        'Rapid Acceleration': data.filter(record => record.rapid_acceleration).length,
        'Extended Idle Time': data.filter(record => record.idle_time > 15).length
    };

    new Chart(document.getElementById('behaviorIncidentsChart'), {
        type: 'pie',
        data: {
            labels: Object.keys(incidents),
            datasets: [{
                data: Object.values(incidents),
                backgroundColor: [
                    'rgba(255, 99, 132, 0.7)',
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(255, 206, 86, 0.7)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 2,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: {
                            size: 11
                        }
                    }
                },
                title: {
                    display: true,
                    text: 'Behavior Incidents Distribution',
                    font: {
                        size: 14
                    }
                }
            }
        }
    });
}

// Fetch data every 30 seconds
fetchDriverBehavior();
setInterval(fetchDriverBehavior, 10000);
