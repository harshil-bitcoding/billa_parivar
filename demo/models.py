from django.db import models
from django.contrib.auth.models import AbstractUser

class DemoState(models.Model):
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self): return self.name

class DemoDistrict(models.Model):
    state = models.ForeignKey(DemoState, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self): return self.name

class DemoTaluka(models.Model):
    district = models.ForeignKey(DemoDistrict, on_delete=models.CASCADE, related_name='talukas')
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self): return self.name

class DemoVillage(models.Model):
    taluka = models.ForeignKey(DemoTaluka, on_delete=models.CASCADE, related_name='villages')
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self): return self.name

class DemoCountry(models.Model):
    name = models.CharField(max_length=100, unique=True)
    guj_name = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self): return self.name

class DemoSurname(models.Model):
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=100, blank=True, null=True)
    top_member = models.ForeignKey('DemoPerson', on_delete=models.SET_NULL, null=True, blank=True, related_name='surname_top')

    def __str__(self):
        return self.name

class DemoPerson(models.Model):
    """Simplified person model for demo"""
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    surname = models.ForeignKey(DemoSurname, on_delete=models.SET_NULL, null=True)
    mobile_number1 = models.CharField(max_length=50, unique=True)
    mobile_number2 = models.CharField(max_length=50, blank=True, null=True)
    date_of_birth = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    out_of_address = models.CharField(max_length=500, blank=True, null=True)
    state = models.ForeignKey(DemoState, on_delete=models.SET_NULL, null=True, blank=True)
    district = models.ForeignKey(DemoDistrict, on_delete=models.SET_NULL, null=True, blank=True)
    taluka = models.ForeignKey(DemoTaluka, on_delete=models.SET_NULL, null=True, blank=True)
    village = models.ForeignKey(DemoVillage, on_delete=models.SET_NULL, null=True)
    profile_pic = models.ImageField(upload_to='demo/profiles/', blank=True, null=True)
    flag_show = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_super_admin = models.BooleanField(default=False)
    is_registered_directly = models.BooleanField(default=False)
    platform = models.CharField(max_length=30, default="postman", null=True, blank=True)
    
    # International fields
    is_out_of_country = models.BooleanField(default=False)
    out_of_country = models.ForeignKey(DemoCountry, on_delete=models.SET_NULL, null=True, blank=True)
    country_mobile_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Simple Gujarati translation fields
    guj_first_name = models.CharField(max_length=100, blank=True, null=True)
    guj_middle_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.surname.name if self.surname else ''}"

class DemoParentChildRelation(models.Model):
    parent = models.ForeignKey(DemoPerson, on_delete=models.CASCADE, related_name='children_relations')
    child = models.ForeignKey(DemoPerson, on_delete=models.CASCADE, related_name='parent_relations')

    class Meta:
        unique_together = ('parent', 'child')

class DemoBusinessCategory(models.Model):
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=100, blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name

class DemoBusinessSubCategory(models.Model):
    category = models.ForeignKey(DemoBusinessCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.category.name} > {self.name}"

class DemoBusiness(models.Model):
    title = models.CharField(max_length=255)
    guj_title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()
    category = models.ForeignKey(DemoBusinessCategory, on_delete=models.SET_NULL, null=True)
    subcategory = models.ForeignKey(DemoBusinessSubCategory, on_delete=models.SET_NULL, null=True, blank=True)
    village = models.ForeignKey(DemoVillage, on_delete=models.SET_NULL, null=True)
    contact_mobile = models.CharField(max_length=15)
    owners = models.ManyToManyField(DemoPerson, related_name='demo_businesses')

    def __str__(self):
        return self.title

class DemoNotification(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    is_event = models.BooleanField(default=False)
    village_target = models.ForeignKey(DemoVillage, on_delete=models.SET_NULL, null=True, blank=True)
    surname_target = models.ForeignKey(DemoSurname, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
