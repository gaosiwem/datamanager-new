from django.test import SimpleTestCase

from performance.admin import parse_eqprs_csv


class ParseEqprsCsvTests(SimpleTestCase):
    def test_skips_metadata_rows_before_header(self):
        csv_text = (
            "ReportTitle,Textbox95,Textbox80\n"
            "QPR for FY 2026-27 National Institutions Oversight Performance Report\n"
            "\n"
            "Sector,Institution,Programme,Frequency,Indicator,Type,SubType,Outcome,Cluster,"
            "Target_Q1,ActualOutput_Q1,ReasonforDeviation_Q1,CorrectiveAction_Q1,"
            "Target_Q2,ActualOutput_Q2,ReasonforDeviation_Q2,CorrectiveAction_Q2,"
            "Target_Q3,ActualOutput_Q3,ReasonforDeviation_Q3,CorrectiveAction_Q3,"
            "Target_Q4,ActualOutput_Q4,ReasonforDeviation_Q4,CorrectiveAction_Q4,"
            "AnnualTarget_Summary2,PrelimaryAudited_Summary2,ReasonforDeviation_Summary,"
            "CorrectiveAction_Summary,ValidatedAudited_Summary2,UID\n"
            "Test Sector,Test Institution,National,Annually,Test Indicator,Standardized,"
            "Not Applicable,Outcome,Cluster,Q1,A1,R1,C1,Q2,A2,R2,C2,Q3,A3,R3,C3,Q4,A4,R4,C4,"
            "Annual,Audited,Annual reason,Annual action,Validated,123\n"
        )

        parsed_data, parsing_error = parse_eqprs_csv(csv_text)

        self.assertIsNone(parsing_error)
        self.assertEqual(len(parsed_data), 1)
        self.assertEqual(parsed_data[0]["Institution"], "Test Institution")
        self.assertEqual(parsed_data[0]["Programme"], "National")

    def test_returns_error_when_required_columns_are_missing(self):
        csv_text = "Sector,Department,Government\nExample,Dept,National\n"

        parsed_data, parsing_error = parse_eqprs_csv(csv_text)

        self.assertIsNone(parsed_data)
        self.assertIn("Institution", parsing_error)
        self.assertIn("Programme", parsing_error)
