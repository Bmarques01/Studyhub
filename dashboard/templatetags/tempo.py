from django import template

register = template.Library()


@register.filter
def horas(minutos):
    """Transforma minutos em texto curto: 45 → '45min', 80 → '1h20', 120 → '2h'.
    Uso no template: {{ total|horas }}"""
    minutos = int(minutos or 0)
    h, m = divmod(minutos, 60)
    if h == 0:
        return f'{m}min'
    return f'{h}h{m:02d}' if m else f'{h}h'
