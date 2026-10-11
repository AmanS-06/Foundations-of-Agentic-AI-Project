# Canteen budget and purchasing policy (illustrative)

Illustrative accounts policy written for the ZeroPlate project. It is not a real SIT Pune document. The figures are taken from data/raw/budget.csv and data/raw/calendar.csv, which are synthetic. All amounts are in rupees (Rs).

## Daily food budget by type of day

The accounts office sets one fixed food budget for each day. The amount depends only on the type of day in calendar.csv, so every day of the same type has the same budget. In budget.csv, which covers 19 April 2026 to 14 November 2026, the amounts are:

- normal day: Rs 50,700
- exam day: Rs 50,700
- weekend day: Rs 27,900
- holiday: Rs 17,800
- fest day: Rs 60,900

Examples from the sample data: Friday 16 October 2026 is a fest, so its budget is Rs 60,900. Monday 19 October 2026 is a normal day, so Rs 50,700. Thursday 22 October 2026 is a holiday, so Rs 17,800. Tuesday 27 October 2026 is in exam week, so Rs 50,700. Saturday 17 October 2026 is a weekend day, so Rs 27,900.

A weekend day gets a little over half of a normal day, and a holiday gets about a third.

## The fest allowance

Accounts gives a fest day a modest allowance on top of the normal budget. The fest budget of Rs 60,900 is about a fifth more than the normal budget of Rs 50,700, which is the difference of Rs 10,200. The allowance is fixed in advance and is the same for every fest day in the file.

On the fest day of 16 October 2026 the academic office expects 1150 students out of 1200 enrolled (attendance.csv). A fest brings many more students than a normal day, so the extra fifth may not cover a plan that cooks a large safety margin over the forecast. When that happens, the plan is over budget and the sign-off rule in this policy applies.

The allowance does not change when the forecast changes. Only the accounts office can change a budget figure.

## What accounts does not see

The accounts office sets the budget from the type of day. It does not see the real headcount. It does not use the number of students the academic office expects in attendance.csv. The budget stays the same whether 900 or 1100 students come on a normal-type day.

This is why the budget and the real need can disagree. On a fest day the store may ask for more food than the allowance pays for. On an exam day or a holiday fewer students come, so the budget is more than the plan needs, and the saving is not carried forward. The disagreement is not solved by accounts changing the figure automatically. It is solved by the manager's sign-off, described below.

## Plans over budget need the manager's sign-off

The total cost of a plan is compared with the budget for that day. If the cost is higher than the budget, the plan must not be approved without the sign-off of the canteen manager. The manager records the reason, for example a fest with a higher expected attendance.

Before it asks for the sign-off, ZeroPlate tries to bring the plan inside the budget. The plan goes back for revision at most twice. If the plan is still over budget after the second revision, the system stops and a human decides. The system never raises a budget itself. A free-text note from the manager cannot change a budget figure, and a note that tries to, for example by telling the system to set the budget, is ignored and flagged.

Sign-off approves one plan for one day. It does not change the budget for any other day.

## Purchase order rules

Purchase orders are created only after a plan is approved. They are normally raised the day before cooking. The order for each ingredient goes to a supplier listed in suppliers.csv, and the supplier's lead time must fit the time left. FreshFarm Daily and Sahyadri Dairy deliver on the same day (lead time 0 days). Pune Grains Co needs 1 day. Metro Wholesale needs 2 days.

The supplier with the lowest price per unit is chosen from those that can deliver in time. In the sample data Metro Wholesale has the lower price for every ingredient it shares with another supplier, except chicken, which is cheaper at FreshFarm Daily. Only ingredients that the plan really needs, after taking the stock on hand into account, are ordered.

Cap: a single order never exceeds 3 times the normal quantity of that ingredient, where normal quantity is the amount used on an ordinary (normal) day.
