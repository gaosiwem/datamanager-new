import uuid
from autoslug import AutoSlugField
from django.db import models
import slugify
from django.contrib.auth.models import User

from budgetportal.models import Department, Government


PFMA_CHOICES = [
    ("1", "1"),
    ("2", "2"),
    ("3A", "3A"),
    ("3B", "3B"),
    ("NL", "Not listed"),
]

FUNCTIONGROUP1_CHOICES = (
    ("GPS", "General public services"),
    ("ED", "Economic development"),
    ("LAC", "Learning and culture"),
    ("SD", "Social development"),
    ("PAS", "Peace and security"),
    ("CD", "Community development"),
    ("H", "Health"),
)

# https://stackoverflow.com/questions/35633037/search-for-document-in-solr-where-a-multivalue-field-is-either-empty
# -or-has-a-sp


def public_entities_file_path(instance, filename):
    return f"public_entities_uploads/{uuid.uuid4()}/{filename}"

def none_selected_query(vocab_name):
    """Match items where none of the options in a custom vocab tag is selected"""
    return '+(*:* NOT %s:["" TO *])' % vocab_name

class PublicEntityManager(models.Manager):
    def get_by_natural_key(
        self, financial_year, sphere_slug, government_slug, public_entity_slug
    ):
        return self.get(
            slug=public_entity_slug,
            government__slug=government_slug,
            government__sphere__slug=sphere_slug,
            government__sphere__financial_year__slug=financial_year,
        )


class PublicEntity(models.Model):
    objects = PublicEntityManager()

    organisational_unit = "public_entity"
    government = models.ForeignKey(
        Government, on_delete=models.CASCADE, related_name="public_entities"
    )
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    name = models.CharField(
        max_length=200,
        help_text="The public entity name must precisely match the text used "
        ". All datasets must be normalised to match this name. Beware that changing "
        "this name might cause a mismatch with already-published datasets which might "
        "need to be update to match this.",
    )
    slug = AutoSlugField(
        populate_from="name", max_length=200, always_update=True, editable=True
    )
    intro = models.TextField(default="", blank=True)

    pfma = models.CharField(
        max_length=10, blank=False, null=False, choices=PFMA_CHOICES
    )
    functiongroup1 = models.CharField(
        max_length=200, blank=True, null=True, choices=FUNCTIONGROUP1_CHOICES
    )

    amount = models.DecimalField(max_digits=20, decimal_places=0, default=0)

    class Meta:
        unique_together = (("government", "slug"), ("government", "name"))
        ordering = ["name"]
        verbose_name_plural = "public entities"

    @classmethod
    def get_in_latest_government(cls, name, government_name):
        """
        Get a public entity instance whose slug matches the provided name slugified,
        in the government with the provided name in the latest financial year.
        Returns None if a matching public entity is not found.
        """
        try:
            return cls.objects.filter(
                slug=slugify(name), government__name=government_name
            ).order_by("-government__sphere__financial_year__slug")[0]
        except IndexError:
            return None

    def get_url_path(self):
        """e.g. 2018-19/national/public-entities/military-veterans"""
        return "/public-entities%s/%s" % (self.government.get_url_path(), self.slug)

    def get_financial_year(self):
        return self.government.sphere.financial_year

    def get_latest_department_instance(self):
        """Try to find the department in the most recent year with the same slug.
        Continue traversing backwards in time until found, or until the original year has been reached.
        """
        newer_public_entities = PublicEntity.objects.filter(
            government__slug=self.government.slug,
            government__sphere__slug=self.government.sphere.slug,
            slug=self.slug,
        ).order_by("-government__sphere__financial_year__slug")
        return newer_public_entities.first() if newer_public_entities else None

    def _get_financial_year_query(self):
        return '+vocab_financial_years:"%s"' % self.get_financial_year().slug

    def _get_government_query(self):
        return none_selected_query("vocab_provinces")

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self.get_url_path())


class PublicEntityExpenditure(models.Model):
    public_entity = models.ForeignKey(PublicEntity, on_delete=models.CASCADE)

    functiongroup2 = models.CharField(
        max_length=200, blank=True, null=True, choices=FUNCTIONGROUP1_CHOICES
    )

    expenditure_type = models.CharField(max_length=200, blank=True, null=True)

    consol_indi = models.CharField(max_length=10, blank=True, null=True)

    economic_classification1 = models.CharField(
        max_length=200, blank=True, null=True)
    economic_classification2 = models.CharField(
        max_length=200, blank=True, null=True)
    economic_classification3 = models.CharField(
        max_length=200, blank=True, null=True)
    economic_classification4 = models.CharField(
        max_length=200, blank=True, null=True)
    economic_classification5 = models.CharField(
        max_length=200, blank=True, null=True)
    economic_classification6 = models.CharField(
        max_length=200, blank=True, null=True)
    budget_phase = models.CharField(max_length=200, blank=True, null=True)

    amount = models.DecimalField(max_digits=20, decimal_places=0)


class PublicEntitiesFileUpload(models.Model):
    user = models.ForeignKey(User, models.DO_NOTHING, blank=True)
    task_id = models.TextField()
    file = models.FileField(upload_to=public_entities_file_path)
    # Plain text listing which departments could not be matched and were not imported
    import_report = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
