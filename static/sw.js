// static/sw.js - Service Worker cho Push Notification
self.addEventListener('push', function(event) {
    const data = event.data ? event.data.json() : {};
    
    const options = {
        body: data.body || 'Bạn có thông báo mới',
        icon: data.icon || '/static/logo.png',
        badge: '/static/badge.png',
        vibrate: [200, 100, 200],
        data: {
            url: data.url || '/'
        },
        actions: [
            { action: 'view', title: 'Xem ngay' },
            { action: 'dismiss', title: 'Để sau' }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'EduSmart', options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    
    if (event.action === 'view' || !event.action) {
        const url = event.notification.data.url;
        event.waitUntil(
            clients.openWindow(url)
        );
    }
});