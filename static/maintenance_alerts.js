// Fetch and display maintenance alerts
async function fetchMaintenanceAlerts() {
    const response = await fetch('/api/maintenance_alerts');
    const data = await response.json();
    updateAlertsTable(data);
    updateAlertCharts(data);
}

function updateAlertsTable(data) {
    console.log('Updating alerts table with data:', data);
    const tbody = document.getElementById('alertsTableBody');
    tbody.innerHTML = '';
    
    data.forEach(alert => {
        console.log('Processing alert:', alert);
        const row = document.createElement('tr');
        const priorityClass = getPriorityClass(alert.priority);
        row.innerHTML = `
            <td style="color: #000;">${alert.vehicle_name}</td>
            <td><span class="badge ${priorityClass}">${alert.alert_type}</span></td>
            <td style="color: #000;">${alert.description}</td>
            <td style="color: #000;">${alert.timestamp}</td>
            <td><span class="badge ${priorityClass}">${alert.priority}</span></td>
            <td><span class="badge bg-${alert.status === 'Open' ? 'warning' : 'success'}">${alert.status}</span></td>
            <td>
                <button class="btn btn-sm ${alert.status === 'Open' ? 'btn-success' : 'btn-warning'}" 
                        onclick="handleAlert(${alert.id}, '${alert.status === 'Open' ? 'Closed' : 'Open'}')">
                    ${alert.status === 'Open' ? 'Resolve' : 'Reopen'}
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function getPriorityClass(priority) {
    switch(priority.toLowerCase()) {
        case 'high': return 'bg-danger';
        case 'medium': return 'bg-warning';
        case 'low': return 'bg-info';
        default: return 'bg-secondary';
    }
}

// Global variables to store chart instances
let alertDistributionChart = null;
let priorityDistributionChart = null;

function updateAlertCharts(data) {
    // Destroy existing charts if they exist
    if (alertDistributionChart) {
        alertDistributionChart.destroy();
        alertDistributionChart = null;
    }
    if (priorityDistributionChart) {
        priorityDistributionChart.destroy();
        priorityDistributionChart = null;
    }

    // Alert Distribution Chart
    const alertTypes = {};
    data.forEach(alert => {
        alertTypes[alert.alert_type] = (alertTypes[alert.alert_type] || 0) + 1;
    });

    const alertDistributionCtx = document.getElementById('alertDistributionChart');
    if (alertDistributionCtx) {
        alertDistributionChart = new Chart(alertDistributionCtx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(alertTypes),
                datasets: [{
                    data: Object.values(alertTypes),
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(75, 192, 192, 0.7)'
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
                            boxWidth: 12
                        }
                    },
                    title: {
                        display: true,
                        text: 'Alert Type Distribution',
                        font: {
                            size: 14
                        }
                    }
                }
            }
        });
    }

    // Priority Distribution Chart
    const priorities = {
        'High': data.filter(alert => alert.priority === 'High' && alert.status === 'Open').length,
        'Medium': data.filter(alert => alert.priority === 'Medium' && alert.status === 'Open').length,
        'Low': data.filter(alert => alert.priority === 'Low' && alert.status === 'Open').length
    };

    const priorityDistributionCtx = document.getElementById('priorityDistributionChart');
    if (priorityDistributionCtx) {
        priorityDistributionChart = new Chart(priorityDistributionCtx, {
            type: 'bar',
            data: {
                labels: Object.keys(priorities),
                datasets: [{
                    label: 'Active Alerts by Priority',
                    data: Object.values(priorities),
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(75, 192, 192, 0.7)'
                    ],
                    borderColor: [
                        'rgba(255, 99, 132, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(75, 192, 192, 1)'
                    ],
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
                        ticks: {
                            stepSize: 1,
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
                        text: 'Active Alerts by Priority',
                        font: {
                            size: 14
                        }
                    }
                }
            }
        });
    }
}

async function handleAlert(alertId, newStatus) {
    console.log('handleAlert called with:', { alertId, newStatus });
    
    // Validate inputs with more robust checks
    if (alertId === undefined || alertId === null || isNaN(alertId)) {
        console.error('Invalid alertId:', alertId);
        alert('Error: Invalid alert ID. Please refresh the page and try again.');
        return;
    }
    
    if (!newStatus || typeof newStatus !== 'string') {
        console.error('Invalid newStatus:', newStatus);
        alert('Error: Invalid status. Please refresh the page and try again.');
        return;
    }

    try {
        console.log(`Attempting to update alert ${alertId} to status: ${newStatus}`);
        const response = await fetch('/api/update_alert_status', {
            method: 'POST',
            credentials: 'same-origin', // Important for session-based authentication
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                alert_id: Number(alertId), // Explicitly convert to number
                status: newStatus
            })
        });
        
        // Parse response text in case JSON parsing fails
        let responseData;
        try {
            responseData = await response.json();
        } catch (parseError) {
            console.error('Failed to parse response JSON:', parseError);
            const responseText = await response.text();
            console.error('Response text:', responseText);
            throw new Error('Failed to parse server response');
        }
        
        // Log full response details
        console.log('Full response:', { 
            status: response.status, 
            ok: response.ok, 
            data: responseData 
        });
        
        if (response.ok) {
            // Refresh the alerts
            await fetchMaintenanceAlerts();
            
            // Optional: Show success message
            alert('Alert status updated successfully!');
        } else {
            // Log and display specific error from server
            console.error('Failed to update alert status:', responseData);
            alert(`Failed to update alert: ${responseData.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Caught error updating alert status:', error);
        alert(`Error updating alert status: ${error.message || 'Please try again'}`);
    }
}

// Fetch data every 30 seconds
fetchMaintenanceAlerts();
setInterval(fetchMaintenanceAlerts, 10000);
