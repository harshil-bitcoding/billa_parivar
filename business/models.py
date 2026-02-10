from django.db import models
from parivar.models import Person, Village, Taluka, District, State


# Language choices for translations
LANGUAGE_CHOICES = [
    ('en', 'English'),
    ('guj', 'Gujarati'),
]


class BusinessCategory(models.Model):
    """
    Business classification system
    Examples: Food & Beverages, Retail, Services, Manufacturing, Agriculture
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, help_text="Category name (English)")
    guj_name = models.CharField(max_length=100, blank=True, null=True, help_text="Category name (Gujarati)")
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Icon key for frontend (e.g., 'food', 'retail')")
    is_active = models.BooleanField(default=True, help_text="Enable/disable category")
    display_order = models.IntegerField(default=0, help_text="Sort order for display")
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = "Business Categories"
    
    def __str__(self):
        return self.name


class Business(models.Model):
    """
    Core business listing model
    Stores business information with location, contact, and metadata
    Supports multiple owners/partners
    """
    id = models.BigAutoField(primary_key=True)
    
    # Ownership (Many-to-Many via BusinessOwner)
    owners = models.ManyToManyField(
        Person,
        through='BusinessOwner',
        related_name='businesses',
        help_text="Business owners/partners"
    )
    
    # Basic Information
    title = models.CharField(max_length=255, help_text="Business name (English default)")
    description = models.TextField(help_text="Business description")
    category = models.ForeignKey(
        BusinessCategory, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='businesses',
        help_text="Business type/category"
    )
    
    # Business Logo/Icon
    logo = models.ImageField(
        upload_to='business_logos/%Y/%m/',
        blank=True,
        null=True,
        help_text="Business logo/icon"
    )
    
    # Search & Discovery
    keywords = models.TextField(
        help_text="Normalized keywords (comma-separated, lowercase)"
    )
    
    # Location (Hierarchical)
    village = models.ForeignKey(
        Village, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='businesses'
    )
    taluka = models.ForeignKey(
        Taluka, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='businesses'
    )
    district = models.ForeignKey(
        District, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='businesses'
    )
    state = models.ForeignKey(
        State, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='businesses'
    )
    
    # Contact Information
    contact_mobile = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        help_text="Primary contact number"
    )
    contact_whatsapp = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        help_text="WhatsApp number (can be same as mobile)"
    )
    
    # Status & Verification
    is_verified = models.BooleanField(
        default=False, 
        help_text="Admin verified business"
    )
    is_active = models.BooleanField(
        default=True, 
        help_text="Visible to users"
    )
    is_deleted = models.BooleanField(
        default=False, 
        help_text="Soft delete flag"
    )
    
    # Analytics & Quality
    profile_score = models.IntegerField(
        default=0, 
        help_text="Completeness score (0-100)"
    )
    views_count = models.IntegerField(
        default=0, 
        help_text="Total profile views"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['village', 'is_active']),
            models.Index(fields=['is_verified', 'is_active']),
        ]
    
    def __str__(self):
        return self.title
    
    def get_primary_owner(self):
        """Get the primary owner of the business"""
        primary = self.owners_set.filter(role='PRIMARY').first()
        return primary.person if primary else None
    
    def save(self, *args, **kwargs):
        # Auto-calculate profile score
        self.profile_score = self.calculate_profile_score()
        
        # Set deleted_at timestamp
        if self.is_deleted and not self.deleted_at:
            from django.utils import timezone
            self.deleted_at = timezone.now()
        elif not self.is_deleted:
            self.deleted_at = None
        
        super().save(*args, **kwargs)
    
    def calculate_profile_score(self):
        """Calculate profile completeness (0-100)"""
        score = 0
        if self.title: score += 20
        if self.description and len(self.description) > 50: score += 20
        if self.category: score += 15
        if self.keywords: score += 10
        if self.contact_mobile or self.contact_whatsapp: score += 15
        if self.village: score += 10
        if self.logo: score += 5
        if hasattr(self, 'images') and self.images.exists(): score += 5
        return min(score, 100)


class BusinessOwner(models.Model):
    """
    Through model for Business-Person many-to-many relationship
    Tracks ownership details and roles
    Supports both registered users and external owners
    """
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="owners_set"
    )

    # Registered owner (optional)
    person = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_businesses"
    )

    # External owner fields (used when person is NULL)
    name = models.CharField(
        max_length=255,
        help_text="Owner name (for external owners or display override)"
    )
    mobile = models.CharField(
        max_length=15,
        help_text="Owner mobile number"
    )

    role = models.CharField(
        max_length=20,
        choices=[
            ("PRIMARY", "Primary Owner"),
            ("PARTNER", "Partner"),
        ],
        default="Primary Owner",
        help_text="Ownership role"
    )

    owner_type = models.CharField(
        max_length=20,
        choices=[
            ("REGISTERED", "Registered User"),
            ("EXTERNAL", "External Owner"),
        ],
        help_text="Type of owner"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Active ownership status"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("business", "person", "mobile")
        ordering = ['-role', 'added_at']  # PRIMARY first, then by date
        verbose_name = "Business Owner"
        verbose_name_plural = "Business Owners"
    
    def __str__(self):
        if self.owner_type == "REGISTERED" and self.person:
            return f"{self.person.first_name} - {self.business.title} ({self.role})"
        return f"{self.name} - {self.business.title} ({self.role})"
    
    @property
    def display_name(self):
        """Returns display name for owner"""
        if self.owner_type == "REGISTERED" and self.person:
            surname = self.person.surname.name if self.person.surname else ''
            return f"{self.person.first_name} {surname}".strip()
        return self.name
    
    @property
    def contact_number(self):
        """Returns contact number for owner"""
        if self.owner_type == "REGISTERED" and self.person:
            return self.person.mobile_number1
        return self.mobile
    
    def save(self, *args, **kwargs):
        # Auto-set owner_type based on person field
        if self.person:
            self.owner_type = "REGISTERED"
            # Auto-populate name and mobile from person if not provided
            if not self.name:
                surname = self.person.surname.name if self.person.surname else ''
                self.name = f"{self.person.first_name} {surname}".strip()
            if not self.mobile:
                self.mobile = self.person.mobile_number1 or ""
        else:
            self.owner_type = "EXTERNAL"
        
        # Validate external owner has name and mobile
        if self.owner_type == "EXTERNAL" and (not self.name or not self.mobile):
            raise ValueError("External owners must have name and mobile")
        
        super().save(*args, **kwargs)


class TranslateBusiness(models.Model):
    """
    Multi-language translations for Business
    Stores Gujarati translations of business information
    """
    id = models.AutoField(primary_key=True)
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='translations'
    )
    language = models.CharField(
        max_length=3,
        choices=LANGUAGE_CHOICES,
        default='guj'
    )
    title = models.CharField(max_length=255, help_text="Translated business name")
    description = models.TextField(help_text="Translated description")
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('business', 'language')
        verbose_name_plural = "Business Translations"
    
    def __str__(self):
        return f"{self.business.title} ({self.language})"


class BusinessImage(models.Model):
    """
    Business image gallery
    Supports multiple images per business with thumbnail generation
    """
    id = models.AutoField(primary_key=True)
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(
        upload_to='business_images/%Y/%m/',
        help_text="Original image"
    )
    thumbnail = models.ImageField(
        upload_to='business_thumbnails/%Y/%m/',
        blank=True,
        null=True,
        help_text="Auto-generated thumbnail (300x300)"
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Cover/featured image"
    )
    display_order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_primary', 'display_order', '-uploaded_at']
    
    def __str__(self):
        return f"Image for {self.business.title}"
    
    def save(self, *args, **kwargs):
        # Auto-generate thumbnail
        if self.image and not self.thumbnail:
            try:
                from PIL import Image
                from io import BytesIO
                from django.core.files.uploadedfile import InMemoryUploadedFile
                
                img = Image.open(self.image)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                
                thumb_io = BytesIO()
                img.save(thumb_io, format='JPEG', quality=85)
                thumb_io.seek(0)
                
                self.thumbnail = InMemoryUploadedFile(
                    thumb_io, None, f"thumb_{self.image.name}",
                    'image/jpeg', thumb_io.getbuffer().nbytes, None
                )
            except Exception as e:
                # If thumbnail generation fails, continue without it
                print(f"Thumbnail generation failed: {e}")
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Delete files from storage
        if self.image:
            self.image.delete(save=False)
        if self.thumbnail:
            self.thumbnail.delete(save=False)
        super().delete(*args, **kwargs)


class BusinessSearchHistory(models.Model):
    """
    User search history tracking
    Used for: notifications, personalization, analytics
    """
    id = models.BigAutoField(primary_key=True)
    person = models.ForeignKey(
        Person, 
        on_delete=models.CASCADE, 
        related_name='business_search_history'
    )
    keyword = models.CharField(
        max_length=255,
        help_text="Raw search term as entered by user"
    )
    normalized_keyword = models.CharField(
        max_length=255,
        help_text="Cleaned/normalized keyword (lowercase, trimmed)"
    )
    searched_at = models.DateTimeField(auto_now_add=True)
    last_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time user was notified about this keyword"
    )
    
    class Meta:
        ordering = ['-searched_at']
        indexes = [
            models.Index(fields=['person', '-searched_at']),
            models.Index(fields=['normalized_keyword']),
        ]
    
    def __str__(self):
        return f"{self.person.first_name} searched '{self.keyword}'"
    
    def save(self, *args, **kwargs):
        # Auto-normalize keyword
        if not self.normalized_keyword:
            self.normalized_keyword = self.keyword.lower().strip()
        super().save(*args, **kwargs)


class SearchIntent(models.Model):
    """
    Keyword synonym mapping for intelligent search
    Example: 'oil' → 'petroleum oil, edible oil, mustard oil, તેલ'
    """
    id = models.AutoField(primary_key=True)
    keyword = models.CharField(
        max_length=100,
        unique=True,
        help_text="Base keyword (normalized)"
    )
    related_terms = models.TextField(
        help_text="Comma-separated synonyms and related terms"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['keyword']
    
    def __str__(self):
        return self.keyword
    
    def get_related_terms_list(self):
        """Returns list of related terms"""
        return [term.strip() for term in self.related_terms.split(',')]


class SearchInterest(models.Model):
    """
    Aggregated search analytics per village
    Tracks trending searches and popular keywords
    """
    id = models.AutoField(primary_key=True)
    keyword = models.CharField(max_length=255)
    village = models.ForeignKey(
        Village,
        on_delete=models.CASCADE,
        related_name='search_interests',
        null=True,
        blank=True,
        help_text="Village scope (null = global)"
    )
    search_count = models.IntegerField(
        default=1,
        help_text="Total number of searches"
    )
    last_searched_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('keyword', 'village')
        ordering = ['-search_count', '-last_searched_at']
        indexes = [
            models.Index(fields=['village', '-search_count']),
        ]
    
    def __str__(self):
        village_name = self.village.name if self.village else "Global"
        return f"{self.keyword} ({village_name}): {self.search_count}"
