from budgetportal.infra_projects import status_order
from budgetportal.models import Dataset, Department, InfraProject
from django.db.models import Count
from django.template.defaultfilters import slugify
from django.urls import reverse
from haystack import indexes


def _compact_text(*values):
    return " ".join(str(value).strip() for value in values if value)


class DepartmentIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True)
    title = indexes.CharField(index_fieldname="title_txt_en")
    snippet = indexes.CharField(index_fieldname="snippet_txt_en", indexed=False, null=True)
    url_path = indexes.CharField(indexed=False)
    financial_year = indexes.CharField(faceted=True)
    sphere = indexes.CharField(faceted=True)
    result_group = indexes.CharField(index_fieldname="result_group_s")
    contributor = indexes.CharField(index_fieldname="contributor_s", indexed=False, default="")
    source_text = indexes.CharField(index_fieldname="source_text_s", indexed=False, default="")
    source_url = indexes.CharField(index_fieldname="source_url_s", indexed=False, default="")

    def get_model(self):
        return Department

    def index_queryset(self, using=None):
        return Department.objects.select_related(
            "government",
            "government__sphere",
            "government__sphere__financial_year",
        ).filter(government__sphere__financial_year__published=True)

    def prepare_text(self, obj):
        return _compact_text(
            obj.name,
            obj.intro,
            obj.government.name,
            obj.government.sphere.name,
            obj.government.sphere.financial_year.slug,
        )

    def prepare_title(self, obj):
        if obj.government.sphere.slug == "national":
            return "National Department: %s" % obj.name
        return "%s Department: %s" % (obj.government.name, obj.name)

    def prepare_snippet(self, obj):
        return (obj.intro or "")[:280]

    def prepare_url_path(self, obj):
        return "/%s" % obj.get_url_path().lstrip("/")

    def prepare_financial_year(self, obj):
        return obj.government.sphere.financial_year.slug

    def prepare_sphere(self, obj):
        return obj.government.sphere.slug

    def prepare_result_group(self, obj):
        return "official"


class DatasetIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True)
    title = indexes.CharField(index_fieldname="title_txt_en")
    snippet = indexes.CharField(index_fieldname="snippet_txt_en", indexed=False, null=True)
    url_path = indexes.CharField(indexed=False)
    financial_year = indexes.CharField(faceted=True)
    result_group = indexes.CharField(index_fieldname="result_group_s")
    organisation = indexes.CharField(index_fieldname="organisation_s")
    dataset_category = indexes.CharField(index_fieldname="dataset_category_s")
    contributor = indexes.CharField(index_fieldname="contributor_s", indexed=False, default="")
    source_text = indexes.CharField(index_fieldname="source_text_s", indexed=False, default="")
    source_url = indexes.CharField(index_fieldname="source_url_s", indexed=False, default="")

    def get_model(self):
        return Dataset

    def index_queryset(self, using=None):
        return Dataset.objects.select_related(
            "financial_year",
            "organisation",
            "dataset_category",
            "sphere",
        ).filter(financial_year__published=True, visibility=True)

    def prepare_text(self, obj):
        return _compact_text(
            obj.title,
            obj.short_description,
            obj.description,
            obj.dataset_category.title if obj.dataset_category_id else "",
            obj.organisation.title if obj.organisation_id else "",
            obj.financial_year.slug if obj.financial_year_id else "",
        )

    def prepare_title(self, obj):
        return obj.title

    def prepare_snippet(self, obj):
        return (obj.short_description or obj.description or "")[:280]

    def prepare_url_path(self, obj):
        return obj.get_url_path()

    def prepare_financial_year(self, obj):
        return obj.financial_year.slug

    def prepare_result_group(self, obj):
        organisation = (obj.organisation.title if obj.organisation_id else "").strip().lower()
        return "official" if organisation == "national treasury" else "contributed"

    def prepare_organisation(self, obj):
        return obj.organisation.title if obj.organisation_id else ""

    def prepare_dataset_category(self, obj):
        return obj.dataset_category.slug if obj.dataset_category_id else ""

    def prepare_contributor(self, obj):
        organisation = obj.organisation.title if obj.organisation_id else ""
        return "" if organisation == "National Treasury" else organisation


class InfraProjectIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True)
    name = indexes.CharField()
    province = indexes.CharField(faceted=True)
    government_label = indexes.CharField(faceted=True)
    sphere = indexes.CharField(faceted=True)
    department = indexes.CharField(faceted=True)
    sector = indexes.CharField(faceted=True)
    status = indexes.CharField(faceted=True)
    status_order = indexes.IntegerField()
    primary_funding_source = indexes.CharField(faceted=True)
    estimated_completion_date = indexes.DateField()
    estimated_total_project_cost = indexes.FloatField()
    latitude = indexes.CharField()
    longitude = indexes.CharField()
    url_path = indexes.CharField()

    irm_snapshot = indexes.CharField(indexed=False)
    project_number = indexes.CharField(indexed=False)
    local_municipality = indexes.CharField(indexed=False)
    district_municipality = indexes.CharField(indexed=False)
    budget_programme = indexes.CharField(indexed=False)
    nature_of_investment = indexes.CharField(indexed=False)
    funding_status = indexes.CharField(indexed=False)
    program_implementing_agent = indexes.CharField(indexed=False)
    principle_agent = indexes.CharField(indexed=False)
    main_contractor = indexes.CharField(indexed=False)
    other_parties = indexes.CharField(indexed=False)
    start_date = indexes.DateField(indexed=False)
    estimated_construction_start_date = indexes.DateField(indexed=False)
    contracted_construction_end_date = indexes.DateField(indexed=False)
    estimated_construction_end_date = indexes.DateField(indexed=False)

    total_professional_fees = indexes.FloatField(indexed=False)
    total_construction_costs = indexes.FloatField(indexed=False)
    variation_orders = indexes.FloatField(indexed=False)
    expenditure_from_previous_years_professional_fees = indexes.FloatField(
        indexed=False
    )
    expenditure_from_previous_years_construction_costs = indexes.FloatField(
        indexed=False
    )
    expenditure_from_previous_years_total = indexes.FloatField(indexed=False)
    main_appropriation_professional_fees = indexes.FloatField(indexed=False)
    adjusted_appropriation_professional_fees = indexes.FloatField(indexed=False)
    main_appropriation_construction_costs = indexes.FloatField(indexed=False)
    adjusted_appropriation_construction_costs = indexes.FloatField(indexed=False)
    main_appropriation_total = indexes.FloatField(indexed=False)
    adjusted_appropriation_total = indexes.FloatField(indexed=False)
    actual_expenditure_q1 = indexes.FloatField(indexed=False)
    actual_expenditure_q2 = indexes.FloatField(indexed=False)
    actual_expenditure_q3 = indexes.FloatField(indexed=False)
    actual_expenditure_q4 = indexes.FloatField(indexed=False)

    def get_model(self):
        return InfraProject

    def prepare(self, obj):
        self._get_latest_snapshot(obj)
        return super().prepare(obj)

    def _get_latest_snapshot(self, obj):
        snapshot = getattr(obj, "_latest_snapshot_for_index", None)
        if snapshot is None:
            snapshot = obj.project_snapshots.select_related(
                "irm_snapshot",
                "irm_snapshot__sphere",
            ).latest()
            obj._latest_snapshot_for_index = snapshot
        return snapshot

    def _get_snapshot_value(self, obj, attribute_name):
        return getattr(self._get_latest_snapshot(obj), attribute_name)

    def prepare_text(self, obj):
        snapshot = self._get_latest_snapshot(obj)
        return _compact_text(
            snapshot.name,
            snapshot.province,
            snapshot.department,
            snapshot.local_municipality,
            snapshot.district_municipality,
            snapshot.project_number,
            snapshot.budget_programme,
            snapshot.primary_funding_source,
            snapshot.nature_of_investment,
            snapshot.program_implementing_agent,
            snapshot.principle_agent,
            snapshot.main_contractor,
            snapshot.other_parties,
        )

    def prepare_name(self, obj):
        return self._get_snapshot_value(obj, "name")

    def prepare_status(self, obj):
        return self._get_snapshot_value(obj, "status")

    def prepare_status_order(self, obj):
        return status_order.get(self._get_snapshot_value(obj, "status"), 100)

    def prepare_government_label(self, obj):
        return self._get_snapshot_value(obj, "government_label")

    def prepare_province(self, obj):
        return self._get_snapshot_value(obj, "province")

    def prepare_sphere(self, obj):
        return self._get_latest_snapshot(obj).irm_snapshot.sphere.slug

    def prepare_department(self, obj):
        return self._get_snapshot_value(obj, "department")

    def prepare_sector(self, obj):
        return self._get_snapshot_value(obj, "sector")

    def prepare_primary_funding_source(self, obj):
        return self._get_snapshot_value(obj, "primary_funding_source")

    def prepare_estimated_total_project_cost(self, obj):
        return self._get_snapshot_value(obj, "estimated_total_project_cost")

    def prepare_estimated_completion_date(self, obj):
        date = self._get_snapshot_value(obj, "estimated_completion_date")
        if date:
            return date.isoformat()

    def prepare_latitude(self, obj):
        return self._get_snapshot_value(obj, "latitude")

    def prepare_longitude(self, obj):
        return self._get_snapshot_value(obj, "longitude")

    def prepare_url_path(self, obj):
        snapshot = self._get_latest_snapshot(obj)
        slug = slugify("%s %s" % (snapshot.name, snapshot.province))
        return reverse("infra-project-detail", args=[obj.pk, slug])

    def prepare_irm_snapshot(self, obj):
        return str(self._get_latest_snapshot(obj).irm_snapshot)

    def prepare_project_number(self, obj):
        return self._get_snapshot_value(obj, "project_number")

    def prepare_local_municipality(self, obj):
        return self._get_snapshot_value(obj, "local_municipality")

    def prepare_district_municipality(self, obj):
        return self._get_snapshot_value(obj, "district_municipality")

    def prepare_budget_programme(self, obj):
        return self._get_snapshot_value(obj, "budget_programme")

    def prepare_nature_of_investment(self, obj):
        return self._get_snapshot_value(obj, "nature_of_investment")

    def prepare_funding_status(self, obj):
        return self._get_snapshot_value(obj, "funding_status")

    def prepare_program_implementing_agent(self, obj):
        return self._get_snapshot_value(obj, "program_implementing_agent")

    def prepare_principle_agent(self, obj):
        return self._get_snapshot_value(obj, "principle_agent")

    def prepare_main_contractor(self, obj):
        return self._get_snapshot_value(obj, "main_contractor")

    def prepare_other_parties(self, obj):
        return self._get_snapshot_value(obj, "other_parties")

    def prepare_start_date(self, obj):
        return self._get_snapshot_value(obj, "start_date")

    def prepare_estimated_construction_start_date(self, obj):
        return self._get_snapshot_value(obj, "estimated_construction_start_date")

    def prepare_contracted_construction_end_date(self, obj):
        return self._get_snapshot_value(obj, "contracted_construction_end_date")

    def prepare_estimated_construction_end_date(self, obj):
        return self._get_snapshot_value(obj, "estimated_construction_end_date")

    def prepare_total_professional_fees(self, obj):
        return self._get_snapshot_value(obj, "total_professional_fees")

    def prepare_total_construction_costs(self, obj):
        return self._get_snapshot_value(obj, "total_construction_costs")

    def prepare_variation_orders(self, obj):
        return self._get_snapshot_value(obj, "variation_orders")

    def prepare_expenditure_from_previous_years_professional_fees(self, obj):
        return self._get_snapshot_value(
            obj,
            "expenditure_from_previous_years_professional_fees",
        )

    def prepare_expenditure_from_previous_years_construction_costs(self, obj):
        return self._get_snapshot_value(
            obj,
            "expenditure_from_previous_years_construction_costs",
        )

    def prepare_expenditure_from_previous_years_total(self, obj):
        return self._get_snapshot_value(obj, "expenditure_from_previous_years_total")

    def prepare_project_expenditure_total(self, obj):
        return self._get_snapshot_value(obj, "project_expenditure_total")

    def prepare_main_appropriation_professional_fees(self, obj):
        return self._get_snapshot_value(obj, "main_appropriation_professional_fees")

    def prepare_adjusted_appropriation_professional_fees(self, obj):
        return self._get_snapshot_value(
            obj,
            "adjusted_appropriation_professional_fees",
        )

    def prepare_main_appropriation_construction_costs(self, obj):
        return self._get_snapshot_value(
            obj,
            "main_appropriation_construction_costs",
        )

    def prepare_adjusted_appropriation_construction_costs(self, obj):
        return self._get_snapshot_value(
            obj,
            "adjusted_appropriation_construction_costs",
        )

    def prepare_main_appropriation_total(self, obj):
        return self._get_snapshot_value(obj, "main_appropriation_total")

    def prepare_adjusted_appropriation_total(self, obj):
        return self._get_snapshot_value(obj, "adjusted_appropriation_total")

    def prepare_actual_expenditure_q1(self, obj):
        return self._get_snapshot_value(obj, "actual_expenditure_q1")

    def prepare_actual_expenditure_q2(self, obj):
        return self._get_snapshot_value(obj, "actual_expenditure_q2")

    def prepare_actual_expenditure_q3(self, obj):
        return self._get_snapshot_value(obj, "actual_expenditure_q3")

    def prepare_actual_expenditure_q4(self, obj):
        return self._get_snapshot_value(obj, "actual_expenditure_q4")

    def should_update(self, instance, **kwargs):
        return instance.project_snapshots.count()

    def index_queryset(self, using=None):
        return InfraProject.objects.annotate(
            project_snapshots_count=Count("project_snapshots")
        ).filter(project_snapshots_count__gte=1)
