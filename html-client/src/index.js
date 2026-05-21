// Open dashboard based on streamer type
async function openDashboard() {
    try {
        const response = await fetch('/streamer_type');
        if (response.ok) {
            const data = await response.json();
            const dashboardUrl = data.streamer_type === 'liquid' ? '/dashboard_liquid' : '/dashboard';
            window.location.href = dashboardUrl;
        } else {
            // Fallback to standard dashboard if request fails
            window.location.href = '/dashboard';
        }
    } catch (error) {
        console.error('Error getting streamer type:', error);
        // Fallback to standard dashboard on error
        window.location.href = '/dashboard';
    }
}
