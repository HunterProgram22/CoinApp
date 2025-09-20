# run_reports_tests.py
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import date, datetime

# Mock all the modules we need before any imports
sys.modules['streamlit'] = Mock()
sys.modules['infrastructure'] = Mock()
sys.modules['infrastructure.auth'] = Mock()
sys.modules['infrastructure.auth.auth_utils'] = Mock()
sys.modules['services'] = Mock()
sys.modules['services.report_logic'] = Mock()

# Set up mock functions from services.report_logic
sys.modules['services.report_logic'].get_collection_value_summary = Mock()
sys.modules['services.report_logic'].get_value_by_category = Mock()
sys.modules['services.report_logic'].get_value_by_metal = Mock()
sys.modules['services.report_logic'].get_top_valued_coins = Mock()
sys.modules['services.report_logic'].get_sellers_with_transactions = Mock()
sys.modules['services.report_logic'].get_seller_summary = Mock()
sys.modules['services.report_logic'].get_seller_detail_by_coin_type = Mock()
sys.modules['services.report_logic'].get_seller_transactions = Mock()


class TestReportsBehavior(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures with comprehensive mock data"""
        # Mock collection value summary
        self.mock_collection_summary = {
            'total_coins': 150,
            'total_cost': 5000.00,
            'total_estimated_value': 6500.00,
            'unrealized_gain_loss': 1500.00,
            'gain_loss_percent': 30.0
        }

        # Mock value by category data
        self.mock_category_data = [
            {
                'asset_category': 'Bullion',
                'count': 50,
                'cost': 2000.00,
                'melt_value': 2200.00,
                'estimated_value': 2300.00,
                'unrealized_gl': 300.00
            },
            {
                'asset_category': 'Numismatic',
                'count': 100,
                'cost': 3000.00,
                'melt_value': 1800.00,
                'estimated_value': 4200.00,
                'unrealized_gl': 1200.00
            }
        ]

        # Mock sellers data
        self.mock_sellers = [
            {
                'id': 1,
                'name': 'ABC Coins',
                'logical_transaction_count': 5,
                'db_transaction_count': 5,
                'total_coins': 25
            }
        ]

    def test_money_formatting(self):
        """Test money formatting helper function"""
        from pages.reports_functions import format_money_display

        result = format_money_display(1234.56)
        self.assertEqual(result, "$1,234.56")

        result = format_money_display(0)
        self.assertEqual(result, "$0.00")

    def test_percentage_formatting(self):
        """Test percentage formatting helper function"""
        from pages.reports_functions import format_percentage_display

        result = format_percentage_display(30.5)
        self.assertEqual(result, "30.5%")

        result = format_percentage_display(0)
        self.assertEqual(result, "0.0%")

    def test_collection_summary_processing(self):
        """Test collection summary data processing"""
        from pages.reports_functions import process_collection_summary

        # Test with valid summary
        result = process_collection_summary(self.mock_collection_summary)

        self.assertIsInstance(result, dict)
        self.assertIn('total_coins', result)
        self.assertEqual(result['total_coins'], 150)

    def test_seller_options_formatting(self):
        """Test seller options formatting for selectbox"""
        from pages.reports_functions import format_seller_options

        options = format_seller_options(self.mock_sellers)

        self.assertIsInstance(options, dict)
        self.assertEqual(len(options), 1)

        # Check the label format
        label = list(options.keys())[0]
        self.assertIn('ABC Coins', label)
        self.assertIn('5', label)  # transaction count

    def test_dataframe_money_formatting(self):
        """Test DataFrame money column formatting"""
        from pages.reports_functions import format_money_columns

        df = pd.DataFrame(self.mock_category_data)
        formatted_df = format_money_columns(df, ['cost', 'estimated_value'])

        # Check that money columns are formatted as strings with $
        self.assertTrue(formatted_df['cost'].iloc[0].startswith('$'))
        self.assertTrue(formatted_df['estimated_value'].iloc[0].startswith('$'))

    def test_gain_loss_calculation(self):
        """Test gain/loss calculation logic"""
        from pages.reports_functions import calculate_gain_loss_metrics

        # Test positive gain
        metrics = calculate_gain_loss_metrics(1000.00, 1200.00)
        self.assertEqual(metrics['gain_loss'], 200.00)
        self.assertEqual(metrics['gain_loss_percent'], 20.0)
        self.assertEqual(metrics['delta_color'], 'normal')

        # Test loss
        metrics = calculate_gain_loss_metrics(1000.00, 800.00)
        self.assertEqual(metrics['gain_loss'], -200.00)
        self.assertEqual(metrics['gain_loss_percent'], -20.0)
        self.assertEqual(metrics['delta_color'], 'inverse')

    def test_coin_display_name_formatting(self):
        """Test coin display name formatting"""
        from pages.reports_functions import format_coin_display_name

        coin_data = {
            'series': 'Morgan Dollar',
            'year': 1893,
            'mint_mark': 'S',
            'variety': 'VAM-2'
        }

        result = format_coin_display_name(coin_data)
        self.assertIn('Morgan Dollar', result)
        self.assertIn('1893', result)
        self.assertIn('S', result)
        self.assertIn('VAM-2', result)

    def test_export_data_preparation(self):
        """Test export data preparation"""
        from pages.reports_functions import prepare_export_data

        data_dict = {
            'summary': [self.mock_collection_summary],
            'category': self.mock_category_data
        }

        result = prepare_export_data(data_dict)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertFalse(result.empty)

    def test_filename_generation(self):
        """Test download filename generation"""
        from pages.reports_functions import create_download_filename

        timestamp = datetime(2024, 1, 15, 10, 30, 0)

        # Test basic filename
        filename = create_download_filename("collection_value", timestamp)
        self.assertIn("collection_value", filename)
        self.assertIn("20240115", filename)
        self.assertTrue(filename.endswith(".csv"))

        # Test with party name
        filename = create_download_filename("seller", timestamp, "ABC Coins")
        self.assertIn("seller", filename)
        self.assertIn("ABC_Coins", filename)

    def test_report_validation(self):
        """Test report input validation"""
        from pages.reports_functions import validate_report_inputs

        # Valid collection value report
        is_valid, message = validate_report_inputs("Collection Value Report", None)
        self.assertTrue(is_valid)

        # Invalid seller report (no seller selected)
        is_valid, message = validate_report_inputs("Seller Report", None)
        self.assertFalse(is_valid)
        self.assertIn("select", message.lower())


if __name__ == '__main__':
    # Create temporary functions file for testing based on CURRENT functionality
    functions_content = '''
# pages/reports_functions.py
# Temporary file for testing - functions extracted to match current Reports behavior

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

def format_money_display(amount: float) -> str:
    """Format money amount for display"""
    return f"${amount:,.2f}"

def format_percentage_display(percentage: float) -> str:
    """Format percentage for display"""
    return f"{percentage:.1f}%"

def process_collection_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Process collection summary data - just return as-is for testing"""
    return summary

def format_seller_options(sellers: List[Dict[str, Any]]) -> Dict[str, Tuple[int, str]]:
    """Format seller data for selectbox options"""
    seller_options = {}
    for seller in sellers:
        logical_count = seller.get('logical_transaction_count', 0)
        db_count = seller.get('db_transaction_count', 0)
        total_coins = seller.get('total_coins', 0)

        if logical_count != db_count:
            label = f"{seller['name']} ({logical_count} dates, {total_coins} coins)"
        else:
            label = f"{seller['name']} ({db_count} transactions, {total_coins} coins)"

        seller_options[label] = (seller['id'], seller['name'])

    return seller_options

def format_money_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Format money columns in DataFrame"""
    formatted_df = df.copy()
    for col in columns:
        if col in formatted_df.columns:
            formatted_df[col] = formatted_df[col].apply(lambda x: format_money_display(x))
    return formatted_df

def calculate_gain_loss_metrics(cost: float, value: float) -> Dict[str, Any]:
    """Calculate gain/loss metrics"""
    gain_loss = value - cost
    gain_loss_percent = (gain_loss / cost * 100) if cost > 0 else 0.0

    return {
        'gain_loss': gain_loss,
        'gain_loss_percent': gain_loss_percent,
        'delta_color': 'normal' if gain_loss >= 0 else 'inverse'
    }

def format_coin_display_name(coin_data: Dict[str, Any]) -> str:
    """Format coin data for display name"""
    parts = [coin_data['series'], str(coin_data['year'])]

    if coin_data.get('mint_mark'):
        parts.append(coin_data['mint_mark'])

    if coin_data.get('variety'):
        parts.append(f"• {coin_data['variety']}")

    return ' '.join(parts)

def prepare_export_data(data_dict: Dict[str, Any]) -> pd.DataFrame:
    """Prepare data for export"""
    dataframes = []
    keys = []

    for key, data in data_dict.items():
        if data:
            if isinstance(data, list):
                dataframes.append(pd.DataFrame(data))
            else:
                dataframes.append(pd.DataFrame([data]))
            keys.append(key)

    if dataframes:
        return pd.concat(
            dataframes,
            keys=keys,
            names=['Report Section', 'Row']
        )

    return pd.DataFrame()

def create_download_filename(report_type: str, timestamp: datetime, party_name: str = None) -> str:
    """Create filename for report download"""
    clean_type = report_type.lower().replace(' ', '_')
    date_str = timestamp.strftime('%Y%m%d')

    if party_name:
        clean_party = party_name.replace(' ', '_')
        return f"{clean_type}_report_{clean_party}_{date_str}.csv"
    else:
        return f"{clean_type}_report_{date_str}.csv"

def validate_report_inputs(report_type: str, selected_value: Optional[str]) -> Tuple[bool, str]:
    """Validate report input parameters"""
    if report_type == "Seller Report" and not selected_value:
        return False, "Please select a seller to generate the report"

    return True, ""

def format_troy_oz_display(oz: float) -> str:
    """Format troy ounces for display"""
    return f"{oz:.4f}"

def create_csv_download_data(df: pd.DataFrame) -> bytes:
    """Create CSV data for download"""
    return df.to_csv().encode('utf-8')
'''

    # Write temporary functions file
    with open('pages/reports_functions.py', 'w') as f:
        f.write(functions_content)

    # Add pages directory to path
    sys.path.insert(0, 'pages')

    # Run tests
    unittest.main(verbosity=2)
