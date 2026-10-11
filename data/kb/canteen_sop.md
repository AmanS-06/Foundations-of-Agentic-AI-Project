# Canteen standard operating procedure (illustrative)

Illustrative SOP written for the ZeroPlate project. It is not the real SIT Pune canteen SOP.

The procedure is consistent with the sample data in data/raw (menu.csv, inventory.csv, suppliers.csv, budget.csv, calendar.csv and attendance.csv). Every figure is part of a synthetic dataset.

## Daily planning and who decides

The production plan for a day is made the day before. Three offices provide the facts. The academic office gives the type of day (normal, exam, holiday, fest or weekend), the weather and the number of students expected. The canteen store gives the stock on hand, the recipes and the supplier list. The accounts office gives the daily budget for that type of day.

ZeroPlate collects these facts and proposes how many plates of each dish to cook and what to order. A checking step tests the proposal against the budget, the fairness minimums, the food-safety limits and the limits on how far the plan may differ from the forecast. The canteen manager makes the final decision. The manager may add a short free-text note, for example about an event. The note can add information, but it cannot change a rule, a budget figure or a food-safety limit. A note that tries to do so is ignored and flagged.

Nothing is ordered or cooked from a plan until the checks pass and, where this SOP requires it, the manager approves.

## Receiving and storing stock

When a delivery arrives, a trained person checks the expiry or best-before date, the packaging and the temperature, and compares the quantity with the order. Chilled high-risk food such as chicken, paneer and milk is accepted only at 5 C or below. The date of receipt is written on every lot. The quantity received should match what the plan needs and the space available, which is the idea in section 2.1(i) of the FSSAI catering guide.

Stock is recorded in the inventory list with the quantity, the unit and the expiry date. The sample inventory.csv gives, for each of the 20 ingredients, the stock on hand, the unit (kg or l), the expiry date and the reorder point. When stock falls to the reorder point, the store raises an order. In the sample inventory, mixed_veg, tomato, paneer, chicken, milk and bread expire within one or two days of the plan date, so they are bought in small quantities and often. Rice, dals, flours, oil and sugar keep for months and are ordered in bulk within the order cap.

## Use-first rule: earliest expiry first

The kitchen uses the stock that expires first. When two lots of one ingredient are in the store, the lot with the earlier expiry date is used before the other lot. This is the FEFO idea (first expire, first out) in the FSSAI catering guide, section 2.2(h).

An ingredient expiring within 24 hours is a use-first ingredient, and the planning step tries to plan dishes that use it. In the sample inventory.csv for the morning of 16 October 2026, mixed_veg, tomato and paneer all have the expiry date 2026-10-17. These are the use-first items. The dishes that use them are veg_thali and veg_sandwich (mixed_veg), paneer_curry (paneer and tomato) and veg_sandwich (tomato). Chicken, milk and bread expire on 2026-10-18, and onion on 2026-10-23, so they come next.

An ingredient that is past its expiry date is never used. It is removed and recorded as waste.

## Purchase orders and the 3 times cap

Purchase orders are raised only after the plan is approved, normally the day before cooking. Each ingredient is ordered from a supplier listed in suppliers.csv, and the supplier's lead time must fit. FreshFarm Daily and Sahyadri Dairy deliver on the same day (lead time 0 days). Pune Grains Co needs 1 day. Metro Wholesale needs 2 days. If the lead time is longer than the time left before cooking, that supplier cannot be used for that day.

Among suppliers that can deliver in time, the canteen buys from the cheapest one. In the sample data Metro Wholesale is cheaper than the other listed supplier for every ingredient except chicken, but it needs 2 days.

Cap rule: a single purchase order never exceeds 3 times the normal quantity of that ingredient. Normal quantity means the amount the canteen uses on an ordinary (normal) day. The cap protects the canteen against a wrong forecast or a typing mistake that would buy far too much food. The system never creates an order above the cap.

## Handling leftover cooked food

Leftover cooked food is checked batch by batch before it is offered again. The rules are in the food-safety document (FSSAI catering guide and our project interpretation). In short: a batch older than 24 hours is discarded. A batch kept hot at 65 C or above may be served. A batch kept at room temperature for more than 2 hours is discarded. A batch that has already been reheated once is discarded. A batch chilled correctly, under 24 hours old and never reheated, may be reheated to 75 C and served once.

The staff record, for each leftover batch, the dish, the time it was cooked, how it was kept, its temperature, and the number of reheats. A batch that is blocked is never served, and neither the manager nor a note can overrule that. It is discarded and the waste is recorded.

## Fairness: vegetarian and Jain dishes

At least one vegetarian dish and one Jain dish must be available on every service day, however low the demand is expected to be. The menu.csv file sets a minimum number of plates for these dishes: veg_thali has min_portions 40 and jain_khichdi has min_portions 20. All other dishes have a minimum of 0. These minimums are our own assumption and not a regulation.

The Jain dish is the lowest-selling dish in the data, so a plan that looks only at cost would cut it. The plan may not do that. The Jain dish, jain_khichdi, is made only from rice, moong dal and ghee. It must stay free of onion, potato, tomato and other vegetables, and it must be prepared and served with clean utensils so that none of those ingredients get into it. If the stock for a fairness dish is short, the plan is not approved until the shortage is solved, and the manager is informed.

## Fest, exam and holiday days

The type of day changes how many students come, and the plan follows the calendar and not habit. The old habit was to cook the average of recent same-weekday sales plus 15 percent and to ignore the calendar. In the sample history this wasted food on holidays and ran short on every fest day.

Fest day: for 16 October 2026 (a fest) attendance.csv expects 1150 of the 1200 enrolled students. The budget is 60,900 rupees. Fresh items should come from same-day suppliers, and stock of the perishable ingredients should be checked early.

Exam day: fewer students come. For 27 October 2026 (exam) the expected number is 719, and the budget is the same as a normal day, 50,700 rupees. The plan is smaller than a normal day, and it is compared with past exam days.

Holiday: very few students come. For 22 October 2026 (holiday) the expected number is 163 and the budget is 17,800 rupees. Cook small quantities and keep only the fairness minimums.

Weekend days have a budget of 27,900 rupees. Rain or heat changes what sells, so the weather in calendar.csv is checked as well.

## When a plan needs the manager's approval

The manager's approval is needed in these cases:

1. The total cost of the plan is above the day's budget from budget.csv. The plan must not be approved without the manager's sign-off, and the manager records the reason.
2. The checking step has sent the plan back for revision twice and it still fails a check. After two revisions a human decides.
3. A fairness minimum (veg_thali 40 plates, jain_khichdi 20 plates) cannot be met with the stock and the suppliers available.
4. A fest, exam or holiday day where the forecast is very different from what the budget assumes, so that the plan cannot be made to fit within the budget.

The manager cannot approve a leftover batch that the food-safety rules block, and cannot approve a purchase order above the 3 times cap. A plan that passes every check is approved without further sign-off.
