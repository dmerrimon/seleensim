#!/usr/bin/env python3
"""
Ilana Add-in Pricing Calculator
Interactive tool to model unit economics scenarios
"""

def calculate_unit_economics(
    price_per_user_month,
    users_per_customer,
    ai_cost_per_user,
    infrastructure_cost_per_user,
    monthly_overhead,
    total_users,
    cac_per_customer,
    churn_rate_annual=0.1
):
    """Calculate unit economics for given parameters"""
    
    # Monthly metrics
    monthly_revenue_per_user = price_per_user_month
    monthly_cost_per_user = ai_cost_per_user + infrastructure_cost_per_user
    monthly_gross_margin_per_user = monthly_revenue_per_user - monthly_cost_per_user
    gross_margin_percent = (monthly_gross_margin_per_user / monthly_revenue_per_user) * 100
    
    # Customer metrics
    monthly_revenue_per_customer = monthly_revenue_per_user * users_per_customer
    annual_revenue_per_customer = monthly_revenue_per_customer * 12
    
    # Total business metrics
    total_customers = total_users / users_per_customer
    monthly_total_revenue = monthly_revenue_per_user * total_users
    monthly_total_gross_profit = monthly_gross_margin_per_user * total_users
    monthly_net_profit = monthly_total_gross_profit - monthly_overhead
    
    # Overhead per user
    overhead_per_user = monthly_overhead / total_users if total_users > 0 else 0
    net_margin_per_user = monthly_gross_margin_per_user - overhead_per_user
    
    # LTV calculation (assuming 3% monthly churn = 36% annual)
    monthly_churn = churn_rate_annual / 12
    customer_lifetime_months = 1 / monthly_churn if monthly_churn > 0 else 60
    ltv_per_customer = annual_revenue_per_customer * (customer_lifetime_months / 12)
    
    # LTV:CAC ratio
    ltv_cac_ratio = ltv_per_customer / cac_per_customer if cac_per_customer > 0 else 0
    
    # Payback period (months)
    if monthly_gross_margin_per_user > 0:
        payback_months = cac_per_customer / (monthly_gross_margin_per_user * users_per_customer)
    else:
        payback_months = float('inf')
    
    return {
        'monthly_revenue_per_user': monthly_revenue_per_user,
        'monthly_cost_per_user': monthly_cost_per_user,
        'monthly_gross_margin_per_user': monthly_gross_margin_per_user,
        'gross_margin_percent': gross_margin_percent,
        'monthly_revenue_per_customer': monthly_revenue_per_customer,
        'annual_revenue_per_customer': annual_revenue_per_customer,
        'total_customers': total_customers,
        'monthly_total_revenue': monthly_total_revenue,
        'monthly_total_gross_profit': monthly_total_gross_profit,
        'monthly_net_profit': monthly_net_profit,
        'overhead_per_user': overhead_per_user,
        'net_margin_per_user': net_margin_per_user,
        'ltv_per_customer': ltv_per_customer,
        'ltv_cac_ratio': ltv_cac_ratio,
        'payback_months': payback_months,
        'customer_lifetime_months': customer_lifetime_months
    }

def print_scenario(name, results):
    """Print formatted results for a scenario"""
    print(f"\n🎯 {name}")
    print("=" * 50)
    print(f"💰 Revenue per user/month:     ${results['monthly_revenue_per_user']:,.0f}")
    print(f"💸 Cost per user/month:        ${results['monthly_cost_per_user']:,.0f}")
    print(f"📊 Gross margin per user:      ${results['monthly_gross_margin_per_user']:,.0f} ({results['gross_margin_percent']:.1f}%)")
    print(f"🏢 Revenue per customer/year:  ${results['annual_revenue_per_customer']:,.0f}")
    print(f"📈 Total monthly revenue:      ${results['monthly_total_revenue']:,.0f}")
    print(f"💡 Monthly net profit:         ${results['monthly_net_profit']:,.0f}")
    print(f"⏰ LTV per customer:           ${results['ltv_per_customer']:,.0f}")
    print(f"🎯 LTV:CAC ratio:              {results['ltv_cac_ratio']:.1f}:1")
    print(f"⏳ Payback period:             {results['payback_months']:.1f} months")

def main():
    """Run pricing scenarios"""
    
    print("🚀 Ilana Add-in Unit Economics Calculator")
    print("=" * 60)
    
    # Base assumptions
    ai_cost = 100  # AI/ML costs per user per month
    infra_cost = 25  # Infrastructure costs per user per month
    monthly_overhead = 45000  # Total monthly overhead
    cac = 8000  # Customer acquisition cost
    
    # Scenario 1: Conservative Enterprise
    print("\n" + "🔷" * 20 + " SCENARIOS " + "🔷" * 20)
    
    scenario1 = calculate_unit_economics(
        price_per_user_month=199,
        users_per_customer=25,
        ai_cost_per_user=ai_cost,
        infrastructure_cost_per_user=infra_cost,
        monthly_overhead=monthly_overhead,
        total_users=500,  # 20 customers
        cac_per_customer=cac,
        churn_rate_annual=0.15
    )
    print_scenario("Conservative Enterprise ($199/user, 25 users/customer)", scenario1)
    
    # Scenario 2: Premium Enterprise
    scenario2 = calculate_unit_economics(
        price_per_user_month=299,
        users_per_customer=50,
        ai_cost_per_user=ai_cost,
        infrastructure_cost_per_user=infra_cost,
        monthly_overhead=monthly_overhead,
        total_users=1000,  # 20 customers
        cac_per_customer=cac,
        churn_rate_annual=0.10
    )
    print_scenario("Premium Enterprise ($299/user, 50 users/customer)", scenario2)
    
    # Scenario 3: Scale Scenario
    scenario3 = calculate_unit_economics(
        price_per_user_month=249,
        users_per_customer=75,
        ai_cost_per_user=ai_cost * 0.8,  # Economies of scale
        infrastructure_cost_per_user=infra_cost * 0.7,  # Better pricing at scale
        monthly_overhead=monthly_overhead * 1.5,  # More overhead but more efficiency
        total_users=3750,  # 50 customers
        cac_per_customer=cac * 0.7,  # Better sales efficiency
        churn_rate_annual=0.08
    )
    print_scenario("Scale Scenario ($249/user, 75 users/customer)", scenario3)
    
    # Break-even analysis
    print(f"\n🎯 BREAK-EVEN ANALYSIS")
    print("=" * 50)
    
    breakeven_price = ai_cost + infra_cost
    print(f"💡 Minimum price to cover direct costs: ${breakeven_price}/user/month")
    
    # Calculate minimum users for overhead break-even at different prices
    prices = [199, 249, 299, 399]
    for price in prices:
        gross_margin = price - (ai_cost + infra_cost)
        min_users = monthly_overhead / gross_margin if gross_margin > 0 else float('inf')
        print(f"   At ${price}/user: Need {min_users:.0f} users to break even on overhead")
    
    # Pricing sensitivity analysis
    print(f"\n📊 PRICING SENSITIVITY ANALYSIS")
    print("=" * 50)
    print("Price | Gross Margin | Users Needed | Annual Revenue")
    print("-" * 50)
    
    for price in [149, 199, 249, 299, 349, 399]:
        margin = price - (ai_cost + infra_cost)
        margin_pct = (margin / price * 100) if price > 0 else 0
        users_needed = monthly_overhead / margin if margin > 0 else float('inf')
        annual_rev = price * users_needed * 12 if users_needed != float('inf') else 0
        print(f"${price:3d} | ${margin:3.0f} ({margin_pct:4.1f}%) | {users_needed:8.0f} | ${annual_rev:10,.0f}")
    
    # ROI justification
    print(f"\n💼 CUSTOMER ROI JUSTIFICATION")
    print("=" * 50)
    
    customer_savings_per_protocol = 100000  # Conservative estimate
    protocols_per_year = 4  # Conservative for enterprise customer
    annual_customer_value = customer_savings_per_protocol * protocols_per_year
    
    for price in [199, 249, 299]:
        annual_cost_per_user = price * 12
        roi_multiple = annual_customer_value / annual_cost_per_user
        roi_percent = (roi_multiple - 1) * 100
        print(f"At ${price}/user/month (${annual_cost_per_user:,}/year):")
        print(f"  Customer saves ${annual_customer_value:,}/year")
        print(f"  ROI: {roi_multiple:.1f}x ({roi_percent:,.0f}%)")
        print(f"  Payback: {12/roi_multiple:.1f} months")
        print()

if __name__ == "__main__":
    main()