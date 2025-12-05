"""
API Authentication and Authorization Module
Handles Discord bot API authentication, rate limiting, and permission checking
"""

from functools import wraps
from flask import request, jsonify, current_app
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import time

# Simple in-memory rate limiting (use Redis in production for distributed systems)
_rate_limit_storage = defaultdict(list)

def verify_api_key(api_key: str) -> bool:
    """
    Verify if the provided API key is valid
    
    Args:
        api_key: The API key to verify
        
    Returns:
        bool: True if valid, False otherwise
    """
    configured_key = current_app.config.get('DISCORD_BOT_API_KEY')
    
    if not configured_key:
        current_app.logger.error("DISCORD_BOT_API_KEY not configured in environment")
        return False
    
    # Constant-time comparison to prevent timing attacks
    if len(api_key) != len(configured_key):
        return False
    
    return hashlib.sha256(api_key.encode()).digest() == hashlib.sha256(configured_key.encode()).digest()


def get_client_identifier():
    """Get unique identifier for rate limiting (API key hash or IP)"""
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Bearer '):
        api_key = auth_header[7:]
        # Use hash of API key as identifier
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    
    # Fallback to IP address
    return request.remote_addr or 'unknown'


def check_rate_limit(identifier: str, max_requests: int = 100, window_seconds: int = 60) -> tuple[bool, dict]:
    """
    Check if the request is within rate limits
    
    Args:
        identifier: Unique client identifier
        max_requests: Maximum requests allowed in the window
        window_seconds: Time window in seconds
        
    Returns:
        tuple: (is_allowed, rate_limit_info)
    """
    current_time = time.time()
    window_start = current_time - window_seconds
    
    # Clean old requests
    _rate_limit_storage[identifier] = [
        req_time for req_time in _rate_limit_storage[identifier]
        if req_time > window_start
    ]
    
    # Check limit
    request_count = len(_rate_limit_storage[identifier])
    is_allowed = request_count < max_requests
    
    if is_allowed:
        _rate_limit_storage[identifier].append(current_time)
    
    rate_limit_info = {
        'limit': max_requests,
        'remaining': max(0, max_requests - request_count - (1 if is_allowed else 0)),
        'reset': int(current_time + window_seconds),
        'window': window_seconds
    }
    
    return is_allowed, rate_limit_info


def api_key_required(f):
    """
    Decorator to require valid API key for endpoint access
    
    Usage:
        @app.route('/api/v1/members')
        @api_key_required
        def get_members():
            return jsonify({'members': []})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'success': False,
                'error': 'missing_auth_header',
                'message': 'Authorization header is required'
            }), 401
        
        if not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': 'invalid_auth_format',
                'message': 'Authorization header must be in format: Bearer <api_key>'
            }), 401
        
        api_key = auth_header[7:]  # Remove "Bearer " prefix
        
        if not verify_api_key(api_key):
            current_app.logger.warning(f"Invalid API key attempt from {request.remote_addr}")
            return jsonify({
                'success': False,
                'error': 'invalid_api_key',
                'message': 'Invalid API key'
            }), 401
        
        # Check rate limiting
        client_id = get_client_identifier()
        max_requests = current_app.config.get('API_RATE_LIMIT', 100)
        is_allowed, rate_info = check_rate_limit(client_id, max_requests)
        
        # Add rate limit headers
        response_headers = {
            'X-RateLimit-Limit': str(rate_info['limit']),
            'X-RateLimit-Remaining': str(rate_info['remaining']),
            'X-RateLimit-Reset': str(rate_info['reset'])
        }
        
        if not is_allowed:
            current_app.logger.warning(f"Rate limit exceeded for {client_id}")
            response = jsonify({
                'success': False,
                'error': 'rate_limit_exceeded',
                'message': f'Rate limit exceeded. Try again in {rate_info["window"]} seconds.',
                'rate_limit': rate_info
            })
            response.status_code = 429
            for header, value in response_headers.items():
                response.headers[header] = value
            return response
        
        # Store API key info in request context for logging
        request.api_authenticated = True
        request.rate_limit_info = rate_info
        
        # Execute the actual endpoint
        result = f(*args, **kwargs)
        
        # Add rate limit headers to successful responses
        if isinstance(result, tuple):
            response, status_code = result[0], result[1]
        else:
            response = result
            status_code = 200
        
        if hasattr(response, 'headers'):
            for header, value in response_headers.items():
                response.headers[header] = value
        
        return response, status_code if isinstance(result, tuple) else response
    
    return decorated_function


def log_api_access(endpoint: str, method: str, user_identifier: str = None, 
                   success: bool = True, response_code: int = 200):
    """
    Log API access for audit trail
    
    Args:
        endpoint: API endpoint accessed
        method: HTTP method
        user_identifier: Discord user ID or other identifier
        success: Whether the request was successful
        response_code: HTTP response code
    """
    log_message = (
        f"API Access - {method} {endpoint} | "
        f"User: {user_identifier or 'unknown'} | "
        f"Status: {response_code} | "
        f"Success: {success} | "
        f"IP: {request.remote_addr}"
    )
    
    if success:
        current_app.logger.info(log_message)
    else:
        current_app.logger.warning(log_message)


def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure random API key
    
    Args:
        length: Length of the API key
        
    Returns:
        str: Secure random API key
    """
    import secrets
    return secrets.token_urlsafe(length)


if __name__ == '__main__':
    # Generate a new API key
    print("Generated API Key:")
    print(generate_api_key())
    print("\nAdd this to your .env file:")
    print(f"DISCORD_BOT_API_KEY={generate_api_key()}")
