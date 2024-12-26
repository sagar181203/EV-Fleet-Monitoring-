document.addEventListener("DOMContentLoaded", () => {
    // Get references to the sidebar and toggle button
    const sidebar = document.getElementById("sidebar");
    const toggleBtn = document.getElementById("toggle-btn");

    // Add a click event listener to the toggle button
    toggleBtn.addEventListener("click", () => {
        // Toggle the 'minimized' class on the sidebar
        sidebar.classList.toggle("minimized");
    });
});
