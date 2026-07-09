def validate_tweet(data):
    errors = []
    
    # Validar author_handle
    if 'author_handle' not in data:
        errors.append("author_handle: missing required field")
    elif not data['author_handle']:
        errors.append("author_handle: field is empty, expected a non-empty string")
    
    # Validar content
    if 'content' not in data:
        errors.append("content: missing required field")
    elif len(data.get('content', '')) < 10:
        errors.append(f"content: too short (got {len(data.get('content', ''))} chars, expected at least 10)")
    
    # Validar timestamp
    if 'timestamp' in data and data['timestamp']:
        try:
            # Intentar parsear la fecha
            from datetime import datetime
            datetime.fromisoformat(data['timestamp'])
        except:
            errors.append(f"timestamp: invalid format (got '{data['timestamp']}', expected ISO format)")
    
    # Devolver errores
    if errors:
        return False, "\n".join(errors)
    return True, "All fields valid"