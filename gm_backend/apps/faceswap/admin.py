from django.contrib import admin

from apps.faceswap.models import FaceSwapJob, FaceSwapTemplate

admin.site.register(FaceSwapTemplate)
admin.site.register(FaceSwapJob)
