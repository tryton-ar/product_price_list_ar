# This file is part of product_price_list_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @classmethod
    def get_sale_price(cls, products, quantity=0):
        pool = Pool()
        PriceList = pool.get('product.price_list')
        Uom = pool.get('product.uom')
        Party = pool.get('party.party')

        prices = super().get_sale_price(products, quantity=quantity)

        context = Transaction().context
        if context.get('price_list'):
            price_list = PriceList(context['price_list'])
            uom = None
            if context.get('uom'):
                uom = Uom(context.get('uom'))
            if context.get('customer'):
                customer = Party(context['customer'])
            else:
                customer = None
            for product in products:
                price = price_list.compute(customer, product,
                    prices[product.id], quantity, uom)
                prices[product.id] = price

        return prices
