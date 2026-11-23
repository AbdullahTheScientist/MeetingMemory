"""Assemble answers.json. Answers/citations were chosen after retrieval (mem.py); every quote is re-verified by CODE here
(>=6 words, literal substring within one turn, case/space-insensitive). Failing citations are dropped and reported."""
import json, mem
A = []
def a(qid, ans, *cites):
  A.append((qid, ans, list(cites)))
a("Q01","They dropped speech recognition and kept the LCD screen, because without the LCD they would need a lot of extra buttons and would lose their whole concept (speech recognition had also never really been integrated into the system).",
  ("TS3006d","Okay so we drop the speech. And drop it yeah?"),("TS3006d","We lose our whole concept. Uh so No we just We keep the L_C_D_."),("TS3006d","We need a lot of extra buttons."))
a("Q02","They first leaned towards a spongy rubber case (stress-ball-type material) and ended with a plain solid plastic case. The switch was a cost cut: a plastic case let them keep the LCD within budget. (Medium confidence on the 'first leaned' part.)",
  ("ES2003c","I also have a preference for rubber."),("ES2003d","this was the one that sacrificed the material for the case and for the actual case design."),("ES2003d","going for a plastic solid case, to keep the L_C_D_"))
a("Q03","Speaker B first proposed replacing the titanium, with titanium-coloured plastic. The titanium was not kept: after the cost check the team agreed to ditch it and go plastic.",
  ("TS3009d","Why why don't we replace the titanium with uh"),("TS3009d","So titanium-coloured plastic for the back."),("TS3009d","So we have to use the ditch the titanium, I'm afraid."))
a("Q04","They combined traditional batteries with solar. When the costs were added up the design was far over the 12.50 Euro limit, the solar cell was named as the main cost driver, and Speaker A proposed skipping it (so it was dropped).",
  ("TS3011c","So uh uh just uh the energy source is um the batteries and the solar."),("TS3011d","what makes it very expensive is uh for example the solar cell"))
a("Q05","They first settled on a battery-plus-kinetic combination and ended with plain batteries. Speaker A (the Project Manager) proposed dropping the kinetic part because shaking it is not really innovative; it also cut cost.",
  ("TS3007c","the energy, the combination between battery and kinetic"),("TS3007d","The kinetic thing, can we just skip it, because uh you have to shake it"),("TS3007d","the energy, which uh turn out to be uh batteries"))
a("Q06","The lost-remote feature was shelved ('not worry about that for now'). Speaker C (User Interface Designer) objected: it would be technologically difficult, since a remote lost under a settee can't receive an infrared signal, and it might be just a gimmick.",
  ("ES2008d","we've decided not to worry about that for now"),("ES2008d","I think it would be difficult technologically, because if your if your remote's lost it's probably under the settee"),("ES2008d","I wonder if it's if it's more just a gimmick then anything else."))
a("Q07","Speaker D (marketing) was asked to take the action item to find the cost; the figure D came back with was roughly two to three Euro extra per unit for the display (low-to-medium confidence: the quoted sentence is cut off).",
  ("IS1008c","No. No no p spec It's 'cause we have to find out cost on it."),("IS1008d","if we add approximately two to three Euro per"))
a("Q08","Speaker D raised repetitive strain injury (RSI) from pressing buttons. The team responded by pitching its design as the opposite of RSI-causing remotes (Speaker A's marketing line); the exact mechanism in the design is not clearly stated (low confidence).",
  ("ES2007b","a thing called R_S_I_, so wrist sense"),("ES2007d","our one does the complete opposite"))
a("Q09","They started from a 25 Euro selling price, later settled on a 35 to 50 Euro sales bracket, and Speaker D (marketing) pushed hardest for an exclusive, higher price.",
  ("IS1002b","Twenty-five Euros is the selling price, we really have to innovate here I guess."),("IS1002c","Thirty five to fifty Euros is our sales bracket okay."),("IS1002b","I want I want to market it as exclusive."))
a("Q10","They chose elderly customers, aged sixty to eighty. The reasoning was that new products are mostly designed for younger people, so older people were an under-served focus, plus forty-plus is the biggest share of the population.",
  ("TS3003c","we're going to target uh sixty to to eighty year old customers."),("TS3003b","are designed for uh younger people, uh so maybe we can focus ourself on the elderly people"))
a("Q11","The project manager (Speaker A) said they would check whether 'only for television' meant no DVD control or just no internet features. When it came up again they said they were actually not having DVD, so the remote is TV-only.",
  ("ES2011b","not for D_V_D_ or just not internet type things"),("ES2011c","we're actually not having D_V_D_, that was one of th"))
a("Q12","Voice recognition was taken out of the final design because of cost (it was the item pushing them over budget, and was a bought-on extra); one idea was to offer it later as an upgrade. They said the remote's distinctive look would itself make it easy to find.",
  ("ES2004d","if you take away the voice recognition, then you've got it."),("ES2004d","that was just a bought-on extra, you could just take that out and that would be fine"),("ES2004d","our object is so distinctive that that in itself is gonna make it easier to locate"))
a("Q13","Yes, speech recognition ended up in the final design. They skipped it in meeting b, then in meeting d (their last reversal) decided to put it back in once it proved financially possible.",
  ("TS3004b","we can skip speech recognition uh directly, because it's not reachable for twenty five Euros"),("TS3004d","Okay yeah. Well then then we're gonna put it in."))
a("Q14","The feature was the voice recogniser. Their final costing came to about 8.2 Euro, and it did not include the voice recogniser (no room had been left for it in the financing).",
  ("IS1009c","pending some more research from our industrial engineer on how expensive that is"),("IS1009d","So, we looks like we are well within budget."),("IS1009d","In the financing there was no room for our voice recogniser."))
a("Q15","Their first full costing was 15.5 Euro against a 12.5 Euro limit (about 3 Euro over). They fixed it by removing the LCD display (bringing it to 12.5).",
  ("ES2016d","So our total is fifteen point five."),("ES2016d","Twelve and a half Euros is what supposed to cost us."),("ES2016d","So we may not need the L_C_D_ display?"))
a("Q16","The project manager (Speaker A) favoured a joystick. It was replaced by plain push-buttons (up/down/left/right) in the final costed design, and the special colour was given up at the same time to reach 12.5 Euro.",
  ("TS3010c","Joystick is better. A small one."),("TS3010d","No joystick. Push-buttons. No special colour. Twelve and a half Euros."))
a("Q17","The touch screen was dropped in meeting c; they kept voice recognition instead. The estimate was upwards of 17.50 Euro per remote for the touch screen.",
  ("ES2009c","it's gonna cost us upwards of seventeen fifty Euro per remote"),("ES2009c","We will omit the touch screen in favour of voice recognition."))
a("Q18","They first planned voice recognition so people could find a lost remote; that changed to a simpler sample sensor/speaker finder (clap/whistle-back style). Speaker C suggested marketing it as a 'finder function' rather than as speech recognition. (Medium confidence on the exact replacement mechanism.)",
  ("ES2014d","the only reason we were planning on having the voice recognition was so that they could find the remote if it got lost"),("ES2014c","it might be a good idea to market it as a um finder function"))
a("Q19","They picked wood as the natural material, and it was replaced by plastic; Speaker B suggested the switch (plastic was also essentially free).",
  ("IS1003c","The feeling is natural, so maybe we can stay with wood."),("IS1003d","I think you can transform the wood into plastic, maybe."))
a("Q20","Speaker A (project manager) said they would look into it; the answer reported back was that the remote is just for television.",
  ("ES2008a","It's a good question. Um. I'll look into that."),("ES2008b","Just for television. That's what we're focused on."))
a("Q21","Speaker C. They reported about fifteen (the speaker says 'dollars') for a version with all the functions. The team then decided to build two versions, one with and one without the LCD, because the LCD was too expensive.",
  ("IS1007c","So for my part I will check the prices the um the prices difference"),("IS1007d","the total cost if you if you want all the fuct functionalities will be about uh fifteen dollars"),("IS1007d","we were no not decided whether we wanted to have an L_C_D_ or not because it's too expensive."))
a("Q22","Speaker B suggested a (small) lithium battery. Speaker A countered that lithium is more expensive, and Speaker D had earlier leaned towards a triple A for a thinner body; the final choice was a single lithium battery. (Low confidence on who 'preferred instead' and why.)",
  ("ES2010c","we could do one small lithium, 'cause you know the lithium batteries are doing quite well"),("ES2010c","They're more expensive though, too. Mm."),("ES2010d","Yeah, let's let's do a lithium."))
a("Q23","They kept both headline features, voice recognition and the LCD display, and swapped scrolling for plain push buttons to get under budget.",
  ("ES2006d","we keep voice recognition, we keep L_C_D_ display. We instead of having scrolling we we just push the buttons."))
a("Q24","They first agreed on a battery as the power source. The project manager (Speaker B) liked the idea of adding kinetic power as a backup, but the final design used just a battery.",
  ("ES2002c","I really like the idea of this kinetic thing where you'd have the back-up of the battery"),("ES2002d","Do we have kinetic as well? No. Okay, just battery."))
a("Q25","They decided not to use fruit or vegetable shapes, using fruit colours/patterns on the rubber instead, because a fruit shape could conflict with how comfortable the remote is to hold.",
  ("ES2011d","So it's just colour, and not necessarily the shape of a strawberry."),("ES2011d","conflicts with the comfort of actually holdi holding the"),("ES2011d","no-one wants to hold a remote that's uncomfortable obviously"))
def cite(m, q): 
  return f'[{m}: "{q}"]'
BRIEF = []
def sec(title):
  BRIEF.append("\n" + title)
def pt(text, *cites):
   BRIEF.append("- " + text + " " + " ".join(cite(m,q) for m,q in cites))
sec("BRIEF FOR TEAM TS3012 BEFORE THE FINAL MEETING (d). Built from meetings a, b and c only.")
sec("1. WHAT HAS BEEN DECIDED")
pt("Money: production price about 12.5 Euro, selling price 25 Euro.",("TS3012a","The production price, twelve and a half Euros, approximately."))
pt("Audience: young buyers (under forty), not older people.",("TS3012b","Everything we target is under forty, so."),("TS3012c","Our focus is the young audience. So let's stick to that."))
pt("Energy: regular batteries.",("TS3012c","energy, we choose regular regular batteries"))
pt("Chip: advanced, because the LCD screen needs it.",("TS3012c","it has to be an advanced one now"))
pt("Case material: rubber, colourable (yellow suggested to look flashy and young); wood and titanium are out.",("TS3012c","the material will be rubber, suppose"),("TS3012c","You can make rubber in any colour."),("TS3012c","I would take a yellow remote control. To have it flashy, to have it it's for young people."),("TS3012c","No, wood i wood's not an option."),("TS3012c","we're not d we're not using titanium"))
pt("Headline features: LCD screen and speech recognition, argued to be the features that add new functionality.",("TS3012c","whereas speech recognition and L_C_D_ screen do offer new functionality in your product"))
pt("Scroll-wheel: voted out as having no real added value.",("TS3012c","you could use it for the channels and for the volume"),("TS3012c","I don't see anything missing really"))
sec("2. WHAT CHANGED ALONG THE WAY")
pt("Speech recognition: meeting b called it very hard across many countries and leaned to the LCD; by meeting c both were in the design.",("TS3012b","I think implementing speech recognition is such a small um apparatus, it's very hard to do."),("TS3012b","I think it's L_C_D_ is better now."),("TS3012c","whereas speech recognition and L_C_D_ screen do offer new functionality in your product"))
pt("Price pressure: in b the LCD put the 25 Euro selling price in doubt.",("TS3012b","Oh, we're not going to be able to sell it for twenty-five then, with an L_C_D_ screen."))
pt("Energy: kinetic was the industrial designer's favourite but was rejected (a remote lies still almost all the time), which also ruled out the rechargeable unit.",("TS3012c","My personal uh fav favourite is the kinetic provision"),("TS3012c","remotes lie still I think like ninety nine percent of the time"),("TS3012c","this rules out our unit our rechargeable unit"))
pt("Scroll-wheel: first called cheap if it does not push, then voted out.",("TS3012c","if we take a normal scroll-wheel without the pushing, then it's not expensive"),("TS3012c","I don't see anything missing really"))
sec("3. OPEN ACTIONS (owner)")
pt("Research LCD versus speech recognition: cost and space. Asked by Speaker A (project manager); Speaker C answered 'I'll try to'. Owner not clearly assigned, so confirm.",("TS3012b","Just to do research into both, w what it costs and what it takes for space."))
pt("Everyone to think of a product name (proposed by Speaker C; Speaker B agreed).",("TS3012b","let's give this uh a name, and not like some vague serial number"),("TS3012b","So I think of a name"))
pt("Design sketch for next meeting, requested by Speaker A (addressee not clear in the transcript, likely the UI designer).",("TS3012c","You doodle a doodle us a nice nice design for for the next meeting"))
pt("Costing: no finance information was available to the team.",("TS3012c","I'm not sure if we're if we're gonna get finance anyway"))
sec("4. DISAGREEMENTS STILL OPEN")
pt("Curves: one curve was judged fine for cost, but Speaker C also wanted the whole case curved and B said curved is more trendy. Single versus double curve is not settled.",("TS3012c","I think one curve is uh fine."),("TS3012c","I would curve the whole actually"),("TS3012c","It can be curved, because that yeah, it's a little bit more trendy to be curved."))
pt("Scroll-wheel: Speaker C accepted the vote only as a design flourish and argued it can be flashy without function.",("TS3012c","It's not because it's functional, but it's just to add to the design, to have it flashy."))
pt("Removable cover: raised by Speaker D, but Speaker A said it is not part of the basic design; may be revisited.",("TS3012c","that's not something we're working with in the basic design"))
pt("LCD versus speech recognition on cost and space is still to be researched (see actions).",("TS3012b","we could put a microphone in here for example"))
brief = "\n".join(BRIEF)
out, bad = [], []
for qid, ans, cites in A:
    ok = []
    for m, q in cites:
        (ok if mem.verify(m, q) else bad).append((m, q)) if False else None
        if mem.verify(m, q):
           ok.append({"meeting_id": m, "quote": q})
        else:
           bad.append((qid, m, q))
    out.append({"question_id": qid, "answer": ans, "citations": ok})
import re
for m, q in re.findall(r'\[(TS3012\w): "(.*?)"\]', brief):
    if not mem.verify(m, q):
       bad.append(("BRIEF", m, q))
json.dump({"answers": out, "brief": brief}, open("answers.json", "w"), indent=2)
print("questions:", len(out), "| citations:", sum(len(o["citations"]) for o in out), "| failed:", len(bad))
for b in bad: print("FAIL", b)
