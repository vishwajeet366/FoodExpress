// Global Variables
let userLocation = null;
let currentCreditScore = 70;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initCreditSystem();
    initLocationTracking();
    initEventListeners();
    loadNotifications();
    
    // Check for credit warnings
    checkCreditWarnings();
    
    // Initialize tooltips
    $('[data-toggle="tooltip"]').tooltip();
});

// Initialize Credit System
function initCreditSystem() {
    const scoreElement = document.getElementById('creditScore');
    if (scoreElement) {
        currentCreditScore = parseInt(scoreElement.dataset.score) || 70;
        updateCreditDisplay(currentCreditScore);
    }
}

// Update Credit Display
function updateCreditDisplay(score) {
    const scoreElement = document.getElementById('creditScore');
    const meterPointer = document.querySelector('.meter-pointer');
    
    if (scoreElement) {
        scoreElement.textContent = score;
        
        // Update credit status class
        const statusClass = getCreditStatusClass(score);
        scoreElement.className = `credit-badge ${statusClass}`;
    }
    
    if (meterPointer) {
        // Move pointer based on score (0-100 scale)
        const percentage = Math.min(Math.max(score, 0), 100);
        meterPointer.style.left = `${percentage}%`;
    }
}

// Get Credit Status Class
function getCreditStatusClass(score) {
    if (score >= 90) return 'credit-trusted';
    if (score >= 75) return 'credit-good';
    if (score >= 50) return 'credit-average';
    if (score >= 30) return 'credit-risky';
    return 'credit-blocked';
}

// Check for Credit Warnings
function checkCreditWarnings() {
    if (currentCreditScore < 50) {
        showNotification('Credit Score Warning', 
            `Your credit score is low (${currentCreditScore}). Certain actions may affect your score.`, 
            'warning');
    }
    
    if (currentCreditScore < 30) {
        showNotification('Account Alert', 
            'Your account is at risk of being blocked. Please improve your behavior.', 
            'error');
    }
}

// Initialize Location Tracking
function initLocationTracking() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => {
                userLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                console.log('Location obtained:', userLocation);
            },
            error => {
                console.error('Error getting location:', error);
                // Use default location or show error
                showNotification('Location Error', 
                    'Unable to get your location. Using default location.', 
                    'warning');
                userLocation = { lat: 28.6139, lng: 77.2090 }; // Default to Delhi
            }
        );
    }
}

// Search Restaurants
function searchRestaurants() {
    const query = document.getElementById('searchInput').value;
    const cuisine = document.getElementById('cuisineFilter').value;
    const minRating = document.getElementById('ratingFilter').value;
    
    fetch(`/api/search_restaurants?q=${encodeURIComponent(query)}&cuisine=${cuisine}&min_rating=${minRating}`)
        .then(response => response.json())
        .then(data => {
            displayRestaurants(data.restaurants);
        })
        .catch(error => {
            console.error('Error searching restaurants:', error);
            showNotification('Search Error', 'Unable to search restaurants. Please try again.', 'error');
        });
}

// Display Restaurants
function displayRestaurants(restaurants) {
    const container = document.getElementById('restaurantsContainer');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (!restaurants || restaurants.length === 0) {
        container.innerHTML = '<div class="alert alert-info">No restaurants found.</div>';
        return;
    }
    
    restaurants.forEach(restaurant => {
        const card = createRestaurantCard(restaurant);
        container.appendChild(card);
    });
}

// Create Restaurant Card
function createRestaurantCard(restaurant) {
    const card = document.createElement('div');
    card.className = 'restaurant-card';
    
    const badge = restaurant.trust_badge ? 
        '<span class="restaurant-badge">✓ Trusted</span>' : '';
    
    const ratingStars = '★'.repeat(Math.floor(restaurant.rating)) + 
                       (restaurant.rating % 1 >= 0.5 ? '½' : '') +
                       '☆'.repeat(5 - Math.ceil(restaurant.rating));
    
    card.innerHTML = `
        ${badge}
        <h4>${restaurant.name}</h4>
        <p class="text-muted mb-2">${restaurant.cuisine_type}</p>
        <div class="d-flex justify-content-between align-items-center mb-2">
            <span class="rating-stars">${ratingStars}</span>
            <span class="badge badge-secondary">${restaurant.rating.toFixed(1)}</span>
        </div>
        <p class="text-muted small mb-2">
            <i class="fas fa-clock"></i> ${restaurant.avg_prep_time} min • 
            <i class="fas fa-map-marker-alt"></i> ${calculateDistance(restaurant)} km
        </p>
        <p class="small mb-3">${restaurant.description || 'No description available.'}</p>
        <div class="d-flex justify-content-between align-items-center">
            <span class="${restaurant.is_open ? 'text-success' : 'text-danger'}">
                <i class="fas fa-circle"></i> ${restaurant.is_open ? 'Open' : 'Closed'}
            </span>
            <button class="btn btn-primary btn-sm" onclick="viewMenu(${restaurant.id})">
                View Menu
            </button>
        </div>
    `;
    
    return card;
}

// Calculate Distance
function calculateDistance(restaurant) {
    if (!userLocation || !restaurant.latitude || !restaurant.longitude) {
        return '?';
    }
    
    const R = 6371; // Earth's radius in km
    const dLat = (restaurant.latitude - userLocation.lat) * Math.PI / 180;
    const dLon = (restaurant.longitude - userLocation.lng) * Math.PI / 180;
    const a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(userLocation.lat * Math.PI / 180) * 
        Math.cos(restaurant.latitude * Math.PI / 180) *
        Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    const distance = R * c;
    
    return distance.toFixed(1);
}

// View Restaurant Menu
function viewMenu(restaurantId) {
    fetch(`/api/get_menu/${restaurantId}`)
        .then(response => response.json())
        .then(data => {
            showMenuModal(data.menu, restaurantId);
        })
        .catch(error => {
            console.error('Error loading menu:', error);
            showNotification('Menu Error', 'Unable to load menu. Please try again.', 'error');
        });
}

// Show Menu Modal
function showMenuModal(menuItems, restaurantId) {
    const modalContent = document.getElementById('menuModalContent');
    if (!modalContent) return;
    
    let html = '<div class="row">';
    
    if (!menuItems || menuItems.length === 0) {
        html = '<div class="alert alert-info">No menu items available.</div>';
    } else {
        // Group by category
        const categories = {};
        menuItems.forEach(item => {
            if (!categories[item.category]) {
                categories[item.category] = [];
            }
            categories[item.category].push(item);
        });
        
        for (const [category, items] of Object.entries(categories)) {
            html += `<div class="col-12"><h5 class="mt-3 mb-2">${category}</h5></div>`;
            
            items.forEach(item => {
                html += `
                    <div class="col-md-6 mb-3">
                        <div class="menu-item-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <h6 class="mb-1">${item.name}</h6>
                                    <p class="text-muted small mb-2">${item.description || ''}</p>
                                    <div class="d-flex align-items-center">
                                        <span class="menu-item-price">₹${item.price}</span>
                                        <span class="text-muted ml-3">
                                            <i class="fas fa-clock"></i> ${item.prep_time} min
                                        </span>
                                    </div>
                                </div>
                                <button class="btn btn-outline-primary btn-sm" 
                                        onclick="addToCart(${item.id}, '${item.name}', ${item.price})">
                                    <i class="fas fa-plus"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
    }
    
    html += '</div>';
    modalContent.innerHTML = html;
    
    // Show modal
    $('#menuModal').modal('show');
    
    // Store restaurant ID for order creation
    document.getElementById('menuModal').dataset.restaurantId = restaurantId;
}

// Shopping Cart
let cart = [];

function addToCart(itemId, itemName, price) {
    const existingItem = cart.find(item => item.id === itemId);
    
    if (existingItem) {
        existingItem.quantity++;
    } else {
        cart.push({
            id: itemId,
            name: itemName,
            price: price,
            quantity: 1
        });
    }
    
    updateCartDisplay();
    showNotification('Cart Updated', `${itemName} added to cart`, 'success');
}

function removeFromCart(itemId) {
    cart = cart.filter(item => item.id !== itemId);
    updateCartDisplay();
}

function updateCartDisplay() {
    const cartCount = document.getElementById('cartCount');
    const cartItems = document.getElementById('cartItems');
    const cartTotal = document.getElementById('cartTotal');
    
    if (cartCount) {
        cartCount.textContent = cart.reduce((sum, item) => sum + item.quantity, 0);
    }
    
    if (cartItems) {
        if (cart.length === 0) {
            cartItems.innerHTML = '<div class="text-muted text-center p-3">Your cart is empty</div>';
            cartTotal.textContent = '₹0';
            return;
        }
        
        let html = '';
        let total = 0;
        
        cart.forEach(item => {
            const itemTotal = item.price * item.quantity;
            total += itemTotal;
            
            html += `
                <div class="cart-item d-flex justify-content-between align-items-center mb-2 p-2 border-bottom">
                    <div>
                        <h6 class="mb-0">${item.name}</h6>
                        <small class="text-muted">₹${item.price} × ${item.quantity}</small>
                    </div>
                    <div class="d-flex align-items-center">
                        <span class="mr-3">₹${itemTotal}</span>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeFromCart(${item.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        });
        
        cartItems.innerHTML = html;
        cartTotal.textContent = `₹${total}`;
    }
}

// Place Order
function placeOrder() {
    if (cart.length === 0) {
        showNotification('Cart Empty', 'Please add items to cart before placing order', 'warning');
        return;
    }
    
    const address = document.getElementById('deliveryAddress')?.value;
    const paymentMethod = document.querySelector('input[name="paymentMethod"]:checked')?.value;
    
    if (!address) {
        showNotification('Address Required', 'Please enter delivery address', 'warning');
        return;
    }
    
    if (!paymentMethod) {
        showNotification('Payment Method Required', 'Please select payment method', 'warning');
        return;
    }
    
    const restaurantId = document.getElementById('menuModal')?.dataset.restaurantId;
    if (!restaurantId) {
        showNotification('Error', 'Restaurant not selected', 'error');
        return;
    }
    
    const orderData = {
        restaurant_id: parseInt(restaurantId),
        items: cart.map(item => ({
            id: item.id,
            quantity: item.quantity
        })),
        address: address,
        payment_method: paymentMethod
    };
    
    fetch('/api/create_order', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(orderData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Order Placed', 
                `Order #${data.order_number} placed successfully! Discount applied: ₹${data.discount_applied}`, 
                'success');
            
            // Clear cart
            cart = [];
            updateCartDisplay();
            
            // Close modals
            $('#menuModal').modal('hide');
            $('#cartModal').modal('hide');
            
            // Refresh page or update order list
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showNotification('Order Failed', data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error placing order:', error);
        showNotification('Order Error', 'Unable to place order. Please try again.', 'error');
    });
}

// Update Order Status (Restaurant)
function updateOrderStatus(orderId, status) {
    if (!confirm(`Are you sure you want to mark this order as ${status}?`)) {
        return;
    }
    
    fetch('/api/update_order_status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            order_id: orderId,
            status: status
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Order Updated', `Order status changed to ${status}`, 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showNotification('Update Failed', data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error updating order:', error);
        showNotification('Update Error', 'Unable to update order status', 'error');
    });
}

// Submit Customer Feedback (Restaurant)
function submitCustomerFeedback(orderId) {
    const politeness = document.getElementById(`politeness-${orderId}`)?.value;
    const punctuality = document.getElementById(`punctuality-${orderId}`)?.value;
    const authenticity = document.getElementById(`authenticity-${orderId}`)?.value;
    const comments = document.getElementById(`comments-${orderId}`)?.value;
    
    if (!politeness || !punctuality || !authenticity) {
        showNotification('Feedback Required', 'Please provide all ratings', 'warning');
        return;
    }
    
    fetch('/api/submit_customer_feedback', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            order_id: orderId,
            politeness: parseInt(politeness),
            punctuality: parseInt(punctuality),
            authenticity: parseInt(authenticity),
            comments: comments
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Feedback Submitted', 'Thank you for your feedback', 'success');
            $(`#feedbackModal-${orderId}`).modal('hide');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showNotification('Submission Failed', data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error submitting feedback:', error);
        showNotification('Submission Error', 'Unable to submit feedback', 'error');
    });
}

// Admin: Update Credit Score
function updateCreditScore(userId) {
    const newScore = document.getElementById(`score-${userId}`)?.value;
    const reason = document.getElementById(`reason-${userId}`)?.value;
    
    if (!newScore || newScore < 0 || newScore > 100) {
        showNotification('Invalid Score', 'Please enter a valid score between 0-100', 'warning');
        return;
    }
    
    if (!reason) {
        showNotification('Reason Required', 'Please provide a reason for the score change', 'warning');
        return;
    }
    
    fetch('/api/admin/update_credit_score', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: userId,
            score: parseInt(newScore),
            reason: reason
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Score Updated', 'Credit score updated successfully', 'success');
            $(`#creditModal-${userId}`).modal('hide');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showNotification('Update Failed', data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error updating credit score:', error);
        showNotification('Update Error', 'Unable to update credit score', 'error');
    });
}

// Cancel Order
function cancelOrder(orderId) {
    const reason = prompt('Please enter reason for cancellation:');
    if (!reason) return;
    
    fetch('/api/cancel_order', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            order_id: orderId,
            reason: reason
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Order Cancelled', 'Order has been cancelled', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showNotification('Cancellation Failed', data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error cancelling order:', error);
        showNotification('Cancellation Error', 'Unable to cancel order', 'error');
    });
}

// Load Notifications
function loadNotifications() {
    const notificationsContainer = document.getElementById('notificationsContainer');
    if (!notificationsContainer) return;
    
    // In a real app, this would fetch from API
    notificationsContainer.innerHTML = `
        <div class="notification-item notification-success">
            <div class="d-flex justify-content-between">
                <strong>Welcome Bonus!</strong>
                <small>2 min ago</small>
            </div>
            <p class="mb-0">You received 10% discount for being a new customer!</p>
        </div>
        <div class="notification-item notification-info">
            <div class="d-flex justify-content-between">
                <strong>Credit Score Update</strong>
                <small>1 hour ago</small>
            </div>
            <p class="mb-0">Your credit score increased by 5 points for timely payments.</p>
        </div>
    `;
}

// Show Notification
function showNotification(title, message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show`;
    notification.innerHTML = `
        <strong>${title}</strong> ${message}
        <button type="button" class="close" data-dismiss="alert" aria-label="Close">
            <span aria-hidden="true">&times;</span>
        </button>
    `;
    
    // Add to notifications container or create one
    let container = document.getElementById('notificationsContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notificationsContainer';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    
    container.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Initialize Event Listeners
function initEventListeners() {
    // Search functionality
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchRestaurants();
            }
        });
    }
    
    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            searchRestaurants();
        });
    });
    
    // Update cart when modal opens
    $('#cartModal').on('show.bs.modal', function() {
        updateCartDisplay();
    });
}