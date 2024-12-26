document.addEventListener("DOMContentLoaded", () => {
    const sidebar = document.getElementById("sidebar");
    const content = document.querySelector(".content");
    const toggleBtn = document.getElementById("toggle-btn");
    const menuItems = document.querySelectorAll(".menu a");

    // Function to handle sidebar toggle
    function toggleSidebar() {
        sidebar.classList.toggle("collapsed");
        content.classList.toggle("expanded");
        
        // Save state to localStorage
        const isCollapsed = sidebar.classList.contains("collapsed");
        localStorage.setItem("sidebarCollapsed", isCollapsed);
    }

    // Function to handle responsive behavior
    function handleResponsive() {
        if (window.innerWidth <= 768) {
            sidebar.classList.add("collapsed");
            content.classList.add("expanded");
        } else {
            // Restore previous state for desktop
            const isCollapsed = localStorage.getItem("sidebarCollapsed") === "true";
            sidebar.classList.toggle("collapsed", isCollapsed);
            content.classList.toggle("expanded", isCollapsed);
        }
    }

    // Add click event listener to toggle button
    toggleBtn.addEventListener("click", (e) => {
        e.preventDefault();
        toggleSidebar();
    });

    // Add click event listeners to menu items for mobile
    menuItems.forEach(item => {
        item.addEventListener("click", () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.add("collapsed");
                content.classList.add("expanded");
            }
        });
    });

    // Handle window resize
    let resizeTimer;
    window.addEventListener("resize", () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(handleResponsive, 250);
    });

    // Initialize on page load
    handleResponsive();

    // Add hover functionality for mobile
    if ("ontouchstart" in window) {
        sidebar.addEventListener("touchstart", () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove("collapsed");
                content.classList.remove("expanded");
            }
        });

        document.addEventListener("touchstart", (e) => {
            if (window.innerWidth <= 768 && !sidebar.contains(e.target)) {
                sidebar.classList.add("collapsed");
                content.classList.add("expanded");
            }
        });
    }
});
