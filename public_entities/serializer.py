from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, DecimalField

from .models import PublicEntity
from budgetportal.models.government import Department, Government, Sphere, FinancialYear


class FinancialYearSerializer(ModelSerializer):
    class Meta:
        model = FinancialYear
        fields = ("slug",)


class SphereSerializer(ModelSerializer):
    financial_year = FinancialYearSerializer()

    class Meta:
        model = Sphere
        fields = ("financial_year", "name")


class GovernmentSerializer(ModelSerializer):
    sphere = SphereSerializer()

    class Meta:
        model = Government
        fields = ("sphere", "name")


class DepartmentSerializer(ModelSerializer):
    government = GovernmentSerializer()

    class Meta:
        model = Department
        fields = ("government", "name")


class PublicEntitiesSerializer(ModelSerializer):
    department = DepartmentSerializer()

    # This exposes the annotation from the queryset
    amount = DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = PublicEntity
        fields = "__all__"
        # add the annotated field explicitly
        extra_fields = ["amount"]

    def get_field_names(self, declared_fields, info):
        """
        Ensure `amount` is included even with fields="__all__".
        """
        fields = super().get_field_names(declared_fields, info)
        extra = getattr(self.Meta, "extra_fields", [])
        return fields + extra
