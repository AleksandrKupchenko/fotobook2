from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """Проверка, состоит ли пользователь в определённой группе"""
    return user.groups.filter(name=group_name).exists()
