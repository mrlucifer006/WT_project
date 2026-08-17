/**
 * Event Entry & Pass Management System - Client Logic
 * Handles real-time form validation, QR streaming, timer synchronization, and notifications.
 */

// Regular Expression Validation Patterns
const REGEX_PATTERNS = {
    name: /^[a-zA-Z\s.]{3,50}$/,
    phone: /^[6-9]\d{9}$/,
    duration: /^\d+$/
};

/**
 * Validates participant entry form inputs
 * @param {string} name - Participant full name
 * @param {string} phone - 10-digit mobile number
 * @param {number} duration - Session duration in minutes
 * @returns {object} { isValid: boolean, message: string }
 */
function validateEntryForm(name, phone, duration) {
    if (!REGEX_PATTERNS.name.test(name.trim())) {
        return { isValid: false, message: "Please enter a valid full name (3-50 letters only)." };
    }
    if (!REGEX_PATTERNS.phone.test(phone.trim())) {
        return { isValid: false, message: "Please enter a valid 10-digit Indian mobile number." };
    }
    if (isNaN(duration) || parseInt(duration) < 1) {
        return { isValid: false, message: "Duration must be at least 1 minute." };
    }
    return { isValid: true, message: "Validation successful." };
}

/**
 * Formats duration in minutes to human-readable string
 * @param {number} minutes
 * @returns {string} e.g. "2h 30m"
 */
function formatDuration(minutes) {
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hrs > 0) {
        return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
    }
    return `${mins}m`;
}

/**
 * Calculates remaining countdown time from target timestamp
 * @param {string|Date} endTimeIso
 * @returns {object} { totalSeconds, isExpired, formatted }
 */
function calculateCountdown(endTimeIso) {
    const target = new Date(endTimeIso).getTime();
    const now = new Date().getTime();
    const diff = Math.max(0, Math.floor((target - now) / 1000));
    
    const minutes = Math.floor(diff / 60);
    const seconds = diff % 60;
    
    return {
        totalSeconds: diff,
        isExpired: diff <= 0,
        formatted: `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    };
}
