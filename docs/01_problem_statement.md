# ZeroPlate: problem statement and domain details

Submitted for Foundations of Agentic AI (SIT Pune, B.Tech AIML, faculty Harshal Raut) by Anhad Mahajan and Aman Saxena, on 15 October 2026.

## 1. The problem in one paragraph

Every day a college canteen has to decide how many plates of each dish to cook before it knows how many students will come. If it cooks too much, food and money are thrown away. If it cooks too little, students go without food and the canteen loses sales. The information that would help is spread over three offices. The academic office knows which days are exams, holidays or fests and how many students are expected. The canteen store knows what is in stock and what each dish needs. The accounts office knows the budget. In the process we model, nobody combines these before the cooking quantities are fixed, so the quantities follow habit. ZeroPlate is a small multi-agent system that collects the three kinds of information, proposes cooking and purchase quantities, checks the proposal against budget, fairness and food-safety rules, and sends it back for revision when it fails a check. We build it as a proof of concept on synthetic data, which means data we generate ourselves.

## 2. The domain and why it is cross-domain

The problem sits in campus food operations, and a good plan needs knowledge from three domains that normally do not talk to each other, which are Education, Supply chain and Finance. In the system, each domain is offered to the agents as a separate tool server using MCP, the Model Context Protocol. MCP is a standard way for a program to offer tools and read-only documents to an AI agent, so that the agent can discover and call them without custom code for every connection. An agent here is a program that uses a language model to decide what to do next, calls tools to fetch data or take actions, and passes its result to other agents.

The table shows who would own each department's data in a real college, the data we use, and the decision it changes. The ownership column is our assumption about a typical college, because we have not confirmed how SIT Pune organises these offices.

| Department | Who owns the data in a real college | Data we use (all synthetic) | Decision it changes |
|---|---|---|---|
| Education | The academic office | Calendar of exam, holiday, fest and normal days, weather, expected number of students present | How many plates of each dish to expect |
| Supply chain | The canteen store | Menu, recipes, stock with expiry dates, supplier prices, cooked leftover batches | What can be cooked, what must be ordered, which ingredients to use first, whether a leftover may be served again |
| Finance | The accounts office | Daily budget, cost per plate, rupee cost of past waste | How much can be spent, and what waste costs in rupees |

The three departments disagree in ways that only show up when their data is put side by side. We expect three conflicts, and the agents are built to handle them.

The first is finance against supply on a fest day. A fest brings far more students than usual, so more food is needed, but the accounts office sets the budget by type of day and does not know the real headcount. In our data the fest day budget is ₹60,900 against ₹50,700 for an ordinary Monday, about a fifth more. A plan that is good for supply can therefore be rejected by finance.

The second is supply against food safety. Leftover curry could be served again, which saves money, but food that has stood too long at room temperature is unsafe. The FSSAI catering guide says hot food held below 65°C must be eaten within 2 hours or reheated to 75°C, that gravies, meat, poultry and fish may be reheated only once, and that cooked food should be eaten within 24 hours of preparation.

The third is fairness. Our menu has one Jain dish, and it is the lowest selling item in our data, so a system that only looks at cost would be tempted to remove it. According to a 2021 Pew Research Center survey, 92% of Jains in India are vegetarian and 67% avoid root vegetables, so an ordinary vegetarian dish is not always something a Jain student can eat. We therefore set a minimum number of plates for the Jain dish and for the main vegetarian thali. These minimums are our own assumption and not a regulation.

## 3. How the canteen decides today

What follows is our model of how a typical campus canteen works. It is a modelled process built from general knowledge and from the assumptions in our data generator, and it is not a measurement of the SIT Pune canteen, which we have not yet observed.

1. The manager looks at what sold on the same weekday over the last few weeks and decides roughly how much to cook. In our simulation the cook takes the average of the last three same-weekday sales and adds 15% to be safe.
2. The cook prepares those fixed quantities. The academic office knows whether tomorrow is an exam day, a holiday or a fest, but that knowledge does not reach the canteen in a form it uses.
3. Ingredients are bought as the store runs low, usually by phone or message, and expiry dates are not tracked closely.
4. The accounts office sees the cost of wasted food only when the month is closed.
5. Whatever is left over at the end of the day is mostly thrown away, and reusing it is informal and not checked against food-safety limits.

One more detail makes this process worse than it looks. The canteen only records what it sold, and it cannot sell more than it cooked. When a dish runs out, the record shows the demand as exactly the amount cooked, so the real demand is hidden and the next estimate starts too low. Our generator also stores the true demand so that we can measure this, but a real canteen would not have that column.

## 4. What goes wrong

Every canteen number in this section is synthetic data generated for this project. Our generator replays the habit described above over 180 past days, from 19 April to 15 October 2026, for 10 dishes and 1,200 enrolled students. The calendar dates are illustrative and are not the real SIT Pune calendar. The numbers describe our model of a canteen and not any real one.

Over the 180 days the simulated canteen cooked 267,968 plates. Of these, 39,549 were never sold, which is a waste share of 14.8%. At the same time, 5.7% of the demand was never served, which is 13,745 plates that students wanted and did not get. The wasted plates cost ₹1,082,661 to make, or about ₹10.8 lakh. The first four weeks are a warm-up, because the habit has no earlier sales to look at, and without them the waste share is 12.5%.

The waste and the shortage land on different kinds of days.

| Type of day | Days in the history | Share of cooked plates wasted | Share of demand unmet |
|---|---|---|---|
| Normal weekday | 104 | 10.4% | 5.1% |
| Exam day | 19 | 26.0% | 2.0% |
| Holiday | 4 | 80.2% | 0% |
| Fest | 4 | 0% | 39.0% |

Exam days and holidays waste food because the habit looks only at recent weeks and ignores that fewer students are on campus. Fest days run short for the opposite reason, and on the four fest days the unmet share ranged from 10% to 71%. Holidays and fests have only four days each in the history, so those two rows show the pattern and are not precise estimates.

These synthetic numbers do not prove that real canteens waste this much, so we also use published studies from other countries. The United Nations Environment Programme (UNEP) Food Waste Index Report 2024 estimates that the world wasted 1.05 billion tonnes of food in 2022, about 132 kg per person, and that food service accounted for 28% of it. A weighed study of a university canteen in Tunisia found that 15.9% of the prepared food was wasted, most of it never served, at a cost of 15.2% of the annual budget, and the authors blame poorly managed changes in student numbers. A Finnish study of 51 food-service outlets found that 17.5% of prepared food became waste. Neither study is from India, so they say nothing certain about an Indian canteen, but they show that this pattern has been measured in real canteens elsewhere. Our synthetic 14.8% is of a similar size, but it comes from assumptions we chose, so we treat that as reassuring and nothing more.

## 5. The proposed solution

ZeroPlate is a multi-agent system whose goal is to plan tomorrow's canteen production with minimum waste, no shortages, within budget and within the food-safety rules. Five agents share the work and pass their results to one another through a shared workflow state.

The Planner agent takes the goal, together with an optional free-text note from the canteen manager, and breaks it into subtasks. The Research agent then gathers the facts. It asks the Education server for the type of day, the weather and the expected attendance, asks the Supply server for stock, recipes and suppliers, and searches a small knowledge base of food-safety and canteen rules. It also turns the manager's note into structured events and flags any note that looks like an attempt to give the system new instructions. The Executor agent forecasts the demand for each dish with a few simple methods, combines them, and records how far off the forecast usually is, which we call the spread. It then tries four candidate plans that cook the forecast plus 0%, 5%, 10% and 15%. Trying several branches and keeping the best one is called Tree-of-Thought. To score a candidate, the Executor imagines 500 possible demands around the forecast and counts the plates left over and the plates missing in each. The score is the utility, defined as minus the waste cost minus three times the shortage cost, so a missing plate counts three times as bad as a leftover one. The weight of three is our assumption. The best scoring candidate wins, and the Executor works out the ingredients, the orders and the cost.

The Critic agent is the part that can say no. It checks the plan against six rules and against the required structure of every output.

1. Each dish must be between half and one and a half times its typical quantity on past days of the same type, so that an exam day is compared with exam days.
2. The planned amount must not exceed the forecast by more than 15%, so a cautious cook cannot quietly over-produce.
3. The total cost must stay within the day's budget from the Finance server.
4. The Jain and vegetarian dishes must keep their minimum portions.
5. Every number in the model's written summary must match the tool output within 1%, which guards against invented figures.
6. Leftover reuse must follow the FSSAI limits for time, temperature and number of reheats described earlier.

The Critic gives one of three verdicts, which are approve, revise or escalate. If it says revise, it writes its feedback in words and the plan goes back to the Executor, which changes the plan in response. The loop can run at most twice, and after that a human decides. Once a plan is approved, the fifth agent, Business Automation, writes the kitchen prep sheet, creates the supplier purchase orders and logs the waste cost. It is the only agent allowed to call tools that change something, and the other agents are refused if they try.

This is more than a forecasting script, because a script would return a single number and stop. Here the agents decide which tools to call, combine data owned by different departments, check their own result against independent rules, and revise when the check fails. It is also more than a chatbot, because the system takes actions and does not only answer questions. To be honest about the model's role, the numerical work and the rules are ordinary code, and the language model is used in three places. It reads the manager's note, it breaks the goal into subtasks, and it writes the Critic's feedback, which steers the Executor's revision. For the demonstration we record a local model's answers once and replay them, so the run is fast, works offline and behaves the same each time.

## 6. Existing solutions and what is different

Food-waste tools already exist, and Winnow and Leanpath are two examples. They measure waste at the bin, so a kitchen can see how much was thrown away after the food was cooked. The percentage savings that such companies publish are their own claims, and we do not use them as evidence for our system. As far as we know these tools do not plan the next day's production by combining the academic calendar, the store and the budget, and they do not check a plan against rules before it is acted on. We have not surveyed commercial demand forecasting products, so we do not claim to be the first. What we offer is a small, explainable example of cross-department planning with checks.

## 7. How we will know it works

The idea is to compare our plans with the old habit on days the system has not seen. We will generate a second synthetic dataset with a different random seed and slightly different demand multipliers, so that the forecaster is not tested on data it learned from. For each held-out day we will measure the share of plates wasted, the share of demand unmet and the rupees wasted under the old habit and under ZeroPlate, reported separately for normal, exam, holiday and fest days. We also plan one comparison on the fest scenario between a plain forecasting script and the full set of agents, to show what the Critic loop adds.

The second part is a set of guardrail tests. They include a manager's note that tries to give the system new orders, a summary containing a wrong number, a plan that goes over budget, a leftover batch that is too old to serve, and a tool call by an agent that is not allowed to make it. We report these as tests that pass or fail and not as a percentage of attacks caught, because we write the attacks ourselves.

Every result will come from a simulation on synthetic data. It can show that the method behaves sensibly under our assumptions, and it cannot show what a real canteen would save. These results have not yet been produced, so this document reports none.

## 8. Limitations and future scope

The biggest limitation is that all the canteen data is synthetic. The demand effect of exams, holidays and fests, the shelf life of each dish, the minimum portions for the Jain and vegetarian dishes, the 15% safety margin of the old habit, the weight of three on a shortage and the budget rules are our own assumptions. They are kept in the configuration file and the data generator so that they can be changed. The system models a single canteen, and the process in section 3 has not been checked against the SIT Pune canteen. The food-safety rules come from one FSSAI guide, and the project is not a certified food-safety system. The old-habit numbers depend on a random seed and on only four holiday and four fest days.

For future work, the first step is to replace the synthetic data with real data, starting with a short visit to the canteen for figures on footfall, number of dishes and monthly waste. The second is to add more departments as new MCP servers without rewriting the agents. The third is to apply the same agents to other cafeterias, such as hostel messes, where only the servers change. A longer idea is for canteens to share surplus food with each other.

## 9. References

1. United Nations Environment Programme, Food Waste Index Report 2024, press release of 27 March 2024. https://www.unep.org/news-and-stories/press-release/world-squanders-over-1-billion-meals-day-un-report
2. Ben Ismail et al., 2022, study of food waste in a university canteen in Tunisia. https://doi.org/10.29329/ijiaar.2022.475.9
3. Luke (Natural Resources Institute Finland), results of the Wastestimator project. https://projects.luke.fi/ravintolafoorumi/etusivu/results-from-wastestimator-project/
4. FSSAI, Food Industry Guide to implement GMP/GHP requirements: Catering, October 2017. https://www.fssai.gov.in/upload/uploadfiles/files/Guidance_Document_Catering_Sector_19_01_2018(4).pdf
5. Pew Research Center, Religion and food, 29 June 2021. https://www.pewresearch.org/religion/2021/06/29/religion-and-food/
