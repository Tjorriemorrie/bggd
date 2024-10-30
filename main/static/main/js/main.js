// Timezone settings
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
document.cookie = "django_timezone=" + timezone + "; path=/; SameSite=Lax";
console.log('Timezone set ', timezone)
