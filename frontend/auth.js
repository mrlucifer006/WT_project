// auth.js - Admin Authentication Guard

function getAuthToken() {
    return localStorage.getItem("admin_token");
}

function isAuthenticated() {
    const token = getAuthToken();
    return token !== null && token !== "";
}

function requireAuth() {
    const currentPath = window.location.pathname;
    const isLoginPage = currentPath.endsWith("login.html") || currentPath.endsWith("login");
    
    if (!isAuthenticated() && !isLoginPage) {
        window.location.href = "login.html";
    } else if (isAuthenticated() && isLoginPage) {
        window.location.href = "index.html";
    }
}

function logout() {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    sessionStorage.clear();
    window.location.href = "login.html";
}

// Run auth check immediately upon loading
requireAuth();
