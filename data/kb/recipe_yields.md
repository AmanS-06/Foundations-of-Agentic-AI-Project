# Recipes, costs and shelf lives for every menu dish

Per-plate quantities, costs and prices for the ten dishes in data/raw/menu.csv and data/raw/recipes.csv. All figures are copied from those files. The dataset is synthetic, so every number is an assumption of this project and not a measurement of the SIT Pune canteen. Money is in rupees (Rs).

## How to read these recipe sections

Each section below is named after one dish as spelled in menu.csv. It lists the ingredient quantities for one plate, using the units in recipes.csv (kg for weight, l for litres). To find the amount for a batch, multiply the per-plate quantity by the number of plates planned. The cost per plate in menu.csv is the cost of the ingredients at the cheapest listed supplier plus a cooking overhead for labour and gas, rounded to whole rupees. The selling price is what a student pays. The shelf life in hours is an assumption made for this project about how long a cooked dish stays good. It is not an FSSAI figure, and the FSSAI limits of 2 hours below 65 C and 24 hours since cooking are separate rules described in the food-safety document. The minimum portions figure is the fairness floor, also an assumption, and it is 0 for dishes with no floor.

## veg_thali

veg_thali is a main dish with the diet tag veg. It is the main vegetarian dish and has a fairness floor: the canteen must always make at least the minimum portions listed below. It contains mixed vegetables and is not a Jain dish.

Ingredients for one plate, as in recipes.csv:
- rice: 0.15 kg per plate
- toor_dal: 0.06 kg per plate
- mixed_veg: 0.12 kg per plate
- wheat_flour: 0.06 kg per plate
- oil: 0.01 l per plate

Diet tag: veg
Category: main
Cost per plate: Rs 35
Selling price: Rs 70
Assumed shelf life (assumption): 6 hours
Minimum portions (fairness floor, assumption): 40

## chicken_biryani

chicken_biryani is a main dish with the diet tag nonveg. It is the only non-vegetarian dish on the menu. It contains chicken and onion, so it is not vegetarian and not Jain. As cooked chicken it is high-risk food in the food-safety document.

Ingredients for one plate, as in recipes.csv:
- rice: 0.18 kg per plate
- chicken: 0.15 kg per plate
- oil: 0.02 l per plate
- onion: 0.05 kg per plate

Diet tag: nonveg
Category: main
Cost per plate: Rs 61
Selling price: Rs 110
Assumed shelf life (assumption): 6 hours
Minimum portions (fairness floor, assumption): 0

## jain_khichdi

jain_khichdi is a main dish with the diet tag jain. It is the Jain dish. Its recipe has no onion, no potato, no tomato and no other vegetable at all, and the dataset has no garlic ingredient. It is made only from rice, moong dal and ghee, which keeps it Jain-friendly. It has a fairness floor: the canteen must always make at least the minimum portions listed below.

Ingredients for one plate, as in recipes.csv:
- rice: 0.1 kg per plate
- moong_dal: 0.07 kg per plate
- ghee: 0.01 kg per plate

Diet tag: jain
Category: main
Cost per plate: Rs 28
Selling price: Rs 60
Assumed shelf life (assumption): 6 hours
Minimum portions (fairness floor, assumption): 20

## paneer_curry

paneer_curry is a main dish with the diet tag veg. It is a vegetarian gravy dish. It contains tomato, so it is not a Jain dish. As a gravy it follows the reheat-only-once rule in the food-safety document.

Ingredients for one plate, as in recipes.csv:
- paneer: 0.1 kg per plate
- tomato: 0.1 kg per plate
- butter: 0.015 kg per plate
- wheat_flour: 0.06 kg per plate

Diet tag: veg
Category: main
Cost per plate: Rs 61
Selling price: Rs 90
Assumed shelf life (assumption): 6 hours
Minimum portions (fairness floor, assumption): 0

## dal_rice

dal_rice is a main dish with the diet tag veg. It is a plain vegetarian main dish. It has no onion, tomato or potato, but its diet tag in menu.csv is veg, not jain.

Ingredients for one plate, as in recipes.csv:
- rice: 0.15 kg per plate
- toor_dal: 0.07 kg per plate
- oil: 0.01 l per plate

Diet tag: veg
Category: main
Cost per plate: Rs 27
Selling price: Rs 55
Assumed shelf life (assumption): 6 hours
Minimum portions (fairness floor, assumption): 0

## chole_bhature

chole_bhature is a main dish with the diet tag veg. It is a vegetarian main dish. It contains onion, so it is not a Jain dish. It has the shortest assumed shelf life of the main dishes.

Ingredients for one plate, as in recipes.csv:
- chana: 0.1 kg per plate
- maida: 0.1 kg per plate
- oil: 0.04 l per plate
- onion: 0.04 kg per plate

Diet tag: veg
Category: main
Cost per plate: Rs 30
Selling price: Rs 65
Assumed shelf life (assumption): 4 hours
Minimum portions (fairness floor, assumption): 0

## veg_sandwich

veg_sandwich is a snack dish with the diet tag veg. It is a vegetarian snack. It contains tomato and mixed vegetables, so it is not a Jain dish.

Ingredients for one plate, as in recipes.csv:
- bread: 0.1 kg per plate
- mixed_veg: 0.05 kg per plate
- butter: 0.01 kg per plate
- tomato: 0.03 kg per plate

Diet tag: veg
Category: snack
Cost per plate: Rs 18
Selling price: Rs 40
Assumed shelf life (assumption): 8 hours
Minimum portions (fairness floor, assumption): 0

## samosa

samosa is a snack dish with the diet tag veg. It is a vegetarian snack. It contains potato, so it is not a Jain dish.

Ingredients for one plate, as in recipes.csv:
- maida: 0.05 kg per plate
- potato: 0.08 kg per plate
- oil: 0.03 l per plate

Diet tag: veg
Category: snack
Cost per plate: Rs 11
Selling price: Rs 20
Assumed shelf life (assumption): 8 hours
Minimum portions (fairness floor, assumption): 0

## masala_chai

masala_chai is a beverage dish with the diet tag veg. It is a hot vegetarian beverage made with milk, tea leaves and sugar. It has the shortest assumed shelf life on the menu.

Ingredients for one plate, as in recipes.csv:
- milk: 0.12 l per plate
- tea_leaves: 0.004 kg per plate
- sugar: 0.012 kg per plate

Diet tag: veg
Category: beverage
Cost per plate: Rs 11
Selling price: Rs 20
Assumed shelf life (assumption): 3 hours
Minimum portions (fairness floor, assumption): 0

## cold_coffee

cold_coffee is a beverage dish with the diet tag veg. It is a cold vegetarian beverage made with milk, coffee powder and sugar.

Ingredients for one plate, as in recipes.csv:
- milk: 0.2 l per plate
- coffee_powder: 0.008 kg per plate
- sugar: 0.02 kg per plate

Diet tag: veg
Category: beverage
Cost per plate: Rs 22
Selling price: Rs 40
Assumed shelf life (assumption): 4 hours
Minimum portions (fairness floor, assumption): 0
