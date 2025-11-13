{
    'name': 'Muemue Stock Forecast',
    'version': '17.0',
    'summary': 'Previsión de stock para Muemue',
    'description': """
        Módulo para calcular la previsión de stock basado en ventas históricas
    """,
    'category': 'Inventory',
    'author': 'ESSEDI IT CONSULTING SL',
    'website': 'https://www.essedi.es',
    'depends': ['base', 'stock', 'sale', 'product','purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_forecast_wizard_views.xml',
        'views/stock_order_wizard_views.xml',
        'views/stock_forecast_views.xml'
        
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}