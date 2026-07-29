# Know the Big Picture — Content Formats and Daily Ideas

## Mission

**The world, explained.**

Help ordinary curious people understand one everyday topic at a time. Optimize
for discovery and a satisfying answer—not expertise, textbook completeness, or
technical depth.

## The Six Formats

### 1. Why

Explain the simple cause behind something people notice.

**Story shape**

```text
immediate answer → where the cause starts → what happens → visible result → payoff
```

**Good inputs**

- Why are flamingos pink?
- Why does pineapple burn your tongue?
- Why is matcha expensive?
- Why do onions make you cry?
- Why do bodybuilders eat rice?

**Avoid**

- Questions requiring specialist knowledge to appreciate
- Questions with no recognizable everyday payoff
- Premises that assume a disputed claim is true

### 2. How

Show how something works, changes, or is made.

**Story shape**

```text
starting point → major actions → important transformation → finished result
```

**Good inputs**

- How is olive oil made?
- How is coffee processed?
- How does cheese melt?
- How is maple syrup made?
- How do noise-canceling headphones work?

**Avoid**

- Every minor production step
- Invisible technical detail that does not change the viewer's understanding
- Processes that cannot be shown clearly

### 3. Types

Introduce a curated set of distinct, recognizable varieties.

**Story shape**

```text
title → one variety per slide → one memorable difference per variety
```

**Good inputs**

- 10 Popular Dumplings Around the World
- 8 Coffee Drinks Explained
- 10 Common Types of Rice
- 8 Kitchen Knives and What They Do
- 10 Types of Clouds

Use **4–12 items**. Eight to ten is the preferred range.

Every item must use the same organizing principle. Do not mix types, subtypes,
brands, ingredients, preparation methods, and broad families.

Prefer titles such as “10 Popular Types” over claims such as “Every Type.”

### 4. Comparison

Explain practical differences between related things.

**Story shape**

```text
what they share → matched differences → practical result → who each suits
```

**Good inputs**

- Espresso vs brewed coffee
- Ramen vs pho
- Cast iron vs stainless steel
- Whey vs casein
- Brown rice vs white rice
- Japanese knives vs Western knives

Compare both sides using the same dimensions. Do not declare a universal winner.

### 5. What Is It?

Introduce something viewers recognize but may not understand.

**Story shape**

```text
plain description → what it does → familiar example → why it matters → takeaway
```

**Good inputs**

- What is creatine?
- What is umami?
- What is sourdough?
- What is a Michelin star?
- What is progressive overload?
- What is a UNESCO World Heritage Site?

Answer “Why should I care?” rather than producing a dictionary definition.

### 6. Myth vs Fact

Evaluate a familiar belief without forcing false certainty.

**Story shape**

```text
claim → qualified verdict → what is true → what is misleading → takeaway
```

**Good inputs**

- Does coffee dehydrate you?
- Is Himalayan salt healthier?
- Does eating fat make you fat?
- Is frozen food less nutritious?
- Does shaving make hair grow thicker?
- Does soreness mean a workout worked?

Allowed verdicts:

```text
true
mostly true
partly true
misleading
mostly false
false
depends
```

Preserve important qualifications. Never turn “may” into “does.”

## Topic Areas

Rotate formats across broad editorial series:

- **Food:** ingredients, dishes, drinks, cooking, nutrition, traditions
- **Fitness:** training, recovery, supplements, food, common beliefs
- **Travel:** airports, trains, hotels, passports, places, customs
- **Everyday:** objects, materials, technology, habits, systems
- **Home:** cookware, furniture, flooring, paint, fabrics, appliances
- **Nature:** animals, plants, weather, landscapes, natural materials
- **Fashion:** garments, fabrics, leather, construction, accessories
- **Architecture:** buildings, roofs, windows, bridges, styles

These are topic areas, not content formats. Any area can use several formats.

## A Strong Daily Mix

Generate one idea for each format:

| Format | Daily purpose |
|---|---|
| Why | A surprising cause behind something familiar |
| How | A visual process or transformation |
| Types | A discovery-rich collection |
| Comparison | A distinction people commonly confuse |
| What Is It? | A familiar term people hear but may not understand |
| Myth vs Fact | A widespread belief worth qualifying |

Aim for:

- Immediate recognition
- A clear curiosity gap
- Strong visual potential
- One memorable payoff
- Evergreen relevance
- Ordinary language

Reject ideas that are:

- Too technical before they become interesting
- Dependent on breaking news
- Primarily celebrity, political, or promotional content
- Difficult to visualize
- Nearly identical to a recent topic
- Based on an unsafe or misleading premise

## Reusable Daily Ideation Prompt

Copy this prompt into ChatGPT whenever you want a new daily set:

```text
You are the idea editor for "Know the Big Picture: The world, explained."

Generate six evergreen short-video ideas: exactly one for each format below:
1. Why
2. How
3. Types
4. Comparison
5. What Is It?
6. Myth vs Fact

The audience is ordinary curious people, not specialists. Optimize for immediate
recognition, a strong curiosity gap, visual potential, and a satisfying everyday
payoff. Favor food, fitness, travel, home, nature, fashion, architecture, and
everyday objects.

Rules:
- Use familiar words.
- Avoid news, politics, celebrities, and temporary trends.
- Avoid questions that become interesting only after technical explanation.
- Do not repeat or closely resemble anything in RECENT TOPICS.
- For Types, propose 8-10 distinct items under one consistent classification.
- For Comparison, compare using practical dimensions.
- For Myth vs Fact, do not assume the claim is simply true or false.
- Prefer questions a person might naturally ask while eating, shopping,
  traveling, exercising, cooking, or noticing the world.

For each idea return:
- format
- exact title/input
- topic area
- one-sentence curiosity payoff
- why it will be visually strong

Then rank the six ideas from strongest to weakest and recommend one to produce
today.

RECENT TOPICS:
[paste the last 30-60 titles here]
```

## Daily Record

Maintain a simple list so the idea generator can avoid repetition:

```text
Date | Format | Title | Topic area | Produced?
```

Paste the recent titles into the daily prompt. Thirty to sixty recent titles is
usually enough to prevent obvious repetition while allowing themes to recur from
new angles.

## GitHub Actions Mapping

Add a generated idea to the `VideoQueue` Sheet:

```text
status:             new or pending
format:             why | how | types | comparison | what_is_it | myth_vs_fact
topic:              exact title/input
number_of_items:    4-12 for Types; blank otherwise
youtube_public:     TRUE for public; blank/FALSE for private
publish_instagram:  TRUE to create/validate an Instagram Reel container
voiceover:          blank/TRUE for narration; FALSE for music-only
```

`new` saves an idea without producing it. `pending` approves it for the next
manual or scheduled queue run. For Types, an explicit `number_of_items` wins;
otherwise a leading title number such as `8 Coffee Drinks Explained` is used,
or the count defaults to 5.

Always use a new numeric job ID for a new idea.
