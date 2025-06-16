document.getElementById('profile-form').addEventListener('submit', function(e) {
    e.preventDefault();
    document.getElementById('success-message').style.display = 'block';
});

function confirmDelete() {
    if (confirm("Are you sure you want to delete your account?")) {
        // Logic to delete account goes here.
        alert("Account deleted successfully.");
    }
}
