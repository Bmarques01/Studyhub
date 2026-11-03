from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('pomodoro/', include('pomodoro.urls')),
    path('estudos/', include('estudos.urls')),
    path('calendario/', include('calendario.urls')),
    path('curso/', include('curso.urls')),
    path('projetos/', include('projetos.urls')),
    path('cadernos/', include('cadernos.urls')),
    path('flashcards/', include('flashcards.urls')),
    path('', include('dashboard.urls')),  # página inicial = dashboard
]
