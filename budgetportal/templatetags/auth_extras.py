from django import template


register = template.Library()


@register.filter
def is_admin_login_target(value):
    if not value:
        return False

    target = str(value)
    return "/admin/" in target or "/cms/" in target
