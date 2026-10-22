"""Branded, immutable PDF snapshots built exclusively from server-owned trip data."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import HTTPException

from . import journey, plan_drafts
from .destination_content import KERALA
from .models import Destination, Stay
from agents.schemas import StayOption


def snapshot(db, conversation_id, user):
    work = journey.workspace(db,conversation_id)
    plans = plan_drafts.versions(db,conversation_id)
    if not plans or plans[0].stale:
        raise HTTPException(409,"Confirm the current trip details and generate an outline before creating a Travel Book.")
    plan = deepcopy(plans[0].payload)
    brief = plan["trip_brief"]
    draft = work.data.get("draft",{})
    if work.data.get("confirmed") != journey.fingerprint(draft):
        raise HTTPException(409,"Review and confirm the changed trip details before exporting.")
    rows = plan["agent_results"]
    stay_id = plan.get("selected_stay_id")
    stay = db.get(Stay,stay_id) if stay_id else None
    lodging = dict(id=stay.id,name=stay.name,location=db.get(Destination,stay.destination_id).name,
                   price_per_night_inr=stay.price_inr,nights=brief["duration_days"]-1,status="Selected · availability unverified") if stay else None
    if lodging is None and plan.get("selected_stay_ref"):
        web_stay = next((s for r in rows if r["agent_id"] == "stay_agent" for s in r.get("stay_options", [])
                         if s.get("evidence", {}).get("source") == "tinyfish.web"
                         and plan["selected_stay_ref"] in {
                             plan_drafts.stay_ref(StayOption.model_validate(s)), s["evidence"].get("ref")}), None)
        if web_stay:
            lodging = dict(id=None, name=web_stay["name"], location=web_stay["location"],
                           price_per_night_inr=web_stay["price_per_night_inr"], nights=brief["duration_days"]-1,
                           status="Web research · indicative rate; dates and availability unverified",
                           source_url=web_stay["evidence"]["ref"])
    options = journey.options(db,draft)
    flight = next((f for f in options["flights"] if f["id"] == work.data.get("selections",{}).get("flight")),None)
    budget = deepcopy(plan["budget"])
    # The standard planner excludes intercity transport. Add only an explicitly
    # selected, server-priced sample outbound flight; never imply a return fare.
    if flight:
        amount = flight["price_inr"] * brief["party_size"]
        budget["lines"].append(dict(category="outbound flight",amount_inr=amount,basis="estimate",
                                    note=f"{brief['party_size']} guests; one way, demo fare; taxes/baggage unverified"))
        budget["total_inr"] += amount
    if budget["total_inr"] > brief["budget_total_inr"]:
        raise HTTPException(422,"The selected flight and plan exceed your confirmed total budget. Change selections before exporting.")
    route = list(dict.fromkeys(s.get("location") for d in plan["itinerary"]["days"] for s in d["stops"]
                               if s["kind"] == "attraction" and s.get("location")))
    return dict(trip_id=conversation_id,version=plans[0].version,traveler=user.full_name or user.username,
                title=plan["itinerary"]["title"],brief=brief,preferences=draft,route=route,
                guide=KERALA if brief["destination"] in {"Kerala","Kochi","Munnar","Alleppey"} else None,
                itinerary=plan["itinerary"],stay=lodging,flight=flight,budget=budget,
                agents=[dict(agent=r["agent_id"],execution=r.get("execution")) for r in rows],
                status="Draft · no supplier reservations",notice=("Personal travel draft. Web rates are indicative; dates and availability require supplier confirmation."
                    if any(r.get("execution", {}).get("mode") == "tinyfish" for r in rows if r.get("execution"))
                    else "Personal hackathon travel draft. All catalog inventory and prices are illustrative."),
                photo_attribution="Kerala photograph: Unsplash, photo-1602216056096-3b40cc0c9944. Editorial content: Voyara demo catalog.")


def render_pdf(data, base_url):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.graphics.shapes import Drawing, Polygon, PolyLine, Circle, String
    from reportlab.graphics.barcode.qr import QrCodeWidget

    navy, teal, saffron, pale = [colors.HexColor(v) for v in ("#103551","#11777c","#efa735","#eaf4f3")]
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BookTitle",fontName="Times-Bold",fontSize=34,leading=39,textColor=navy,spaceAfter=15))
    styles.add(ParagraphStyle(name="BookHeading",fontName="Times-Bold",fontSize=23,leading=27,textColor=navy,spaceAfter=15))
    styles.add(ParagraphStyle(name="BookBody",fontName="Helvetica",fontSize=10,leading=15,textColor=navy,spaceAfter=9))
    styles.add(ParagraphStyle(name="BookSmall",fontName="Helvetica",fontSize=8,leading=12,textColor=navy,spaceAfter=7))
    styles.add(ParagraphStyle(name="BookKicker",fontName="Helvetica-Bold",fontSize=9,leading=14,textColor=teal,spaceAfter=13))
    styles.add(ParagraphStyle(name="BookPrice",fontName="Helvetica-Bold",fontSize=26,leading=31,textColor=navy,spaceAfter=15))
    styles.add(ParagraphStyle(name="BookCenter",parent=styles["BookBody"],alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="BookCity",fontName="Times-Bold",fontSize=18,leading=23,textColor=navy,spaceAfter=7))
    out = BytesIO()
    document = SimpleDocTemplate(out,pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,
                                 topMargin=29*mm,bottomMargin=23*mm,title=data["title"],author="Voyara AI Travel Team")
    story = []
    p = lambda text,style="BookBody": Paragraph(escape(str(text).replace("₹","INR ")),styles[style])
    # Use '&' once; Paragraph's XML parser decodes the URL attribute correctly.
    def edit_link(label,section):
        url=base_url.rstrip('/')+'/#'+section+'?tripId='+data["trip_id"]+'&edit=true'
        return Paragraph(f'<link href="{escape(url,{chr(34):"&quot;"})}" color="#11777c">{escape(label)} →</link>',styles["BookBody"])
    def chapter(kicker,title):
        story.extend([p(kicker.upper(),"BookKicker"),p(title,"BookHeading")])
    def table(rows,widths=None):
        t=Table([[p(c,"BookSmall") for c in row] for row in rows],colWidths=widths or [62*mm,112*mm],hAlign="LEFT")
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),pale),('VALIGN',(0,0),(-1,-1),'TOP'),
                               ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),
                               ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
                               ('LINEBELOW',(0,0),(-1,-2),.5,colors.white)]))
        story.extend([t,Spacer(1,6*mm)])
    money=lambda amount:"Price unknown" if amount is None else "INR "+f"{amount:,}"
    brief=data["brief"]
    photo=Path(__file__).resolve().parents[2]/"frontend/public/travel/kerala.jpg"
    chapter("Your personal travel book",f"Your {brief['destination']} Escape")
    story.append(p(data["guide"]["description"] if data["guide"] else "A personal journey, shaped around your confirmed plans and interests."))
    if data["guide"] and photo.exists():
        story.append(Image(str(photo),width=174*mm,height=98*mm))
        story.append(Spacer(1,7*mm))
    table([["Travel dates",brief["start_date"]+" to "+brief["end_date"]],
           ["Duration & travellers",f"{brief['duration_days']} days / {brief['duration_days']-1} nights · {brief['party_size']} travellers"],
           ["Travel style",brief.get("pace") or "Your own pace"],["Status",data["status"]]])
    story.append(p("Awaiting supplier quotes" if not data["budget"].get("costs_complete", True) and not data["budget"]["total_inr"] else money(data["budget"]["total_inr"]),"BookPrice"))
    story.append(p(f"Indicative total for all {brief['party_size']} travellers · listed selections only" if data["budget"].get("costs_complete", True) else "Known-cost subtotal only — trip total unknown; supplier quotes required", "BookSmall"))
    story.append(p("One assumed room; listed meals/activities only. Unselected flights, extra meals, transfers, taxes and supplier availability remain unverified.","BookSmall"))
    story.append(edit_link("Open your saved trip & edit with Voyara AI","travel-book/"+data["trip_id"]))
    story.append(PageBreak())

    chapter("Your destination",f"Discover {brief['destination']}")
    if data["guide"]:
        story.append(p(data["guide"]["description"]))
        city_blocks=[]
        for city in data["guide"]["cities"]:
            city_blocks.extend([p(city["name"],"BookCity"),p(city["description"]),p(" · ".join(city["experiences"]),"BookSmall"),Spacer(1,7*mm)])
        sketch=Drawing(160,300)
        sketch.add(Polygon([40,285,92,294,120,250,108,218,130,175,108,126,136,70,146,25,98,18,79,79,60,116,67,162,45,210],fillColor=colors.HexColor('#cde4cf'),strokeColor=None))
        sketch.add(PolyLine([60,178,109,224,81,77],strokeColor=teal,strokeWidth=2,strokeDashArray=[5,4]))
        for x,y,label,tx,ty in [(60,178,'Kochi',7,179),(109,224,'Munnar',110,239),(81,77,'Alleppey',90,73)]:
            sketch.add(Circle(x,y,6,fillColor=saffron,strokeColor=colors.white,strokeWidth=2))
            sketch.add(String(tx,ty,label,fontName='Helvetica-Bold',fontSize=9,fillColor=navy))
        sketch.add(String(76,144,'KERALA',fontName='Helvetica-Bold',fontSize=9,fillColor=teal))
        sketch.add(String(8,30,'Arabian Sea',fontName='Helvetica',fontSize=8,fillColor=teal))
        regional=Table([[city_blocks,sketch]],colWidths=[112*mm,62*mm],hAlign='LEFT')
        regional.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(1,0),(1,0),pale),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),12)]))
        story.extend([regional,Spacer(1,7*mm)])
        story.append(p("Suggested regional discovery sequence: Kochi → Munnar → Alleppey. The dated itinerary is the source for your selected stops; this is not a verified road route.","BookSmall"))
        story.append(p(data["guide"]["season_note"]))
    else:
        story.append(p("Explore local culture, food and free time around your scheduled experiences. Confirm practical details with the relevant providers."))
    story.append(edit_link("Explore destinations with this trip","destinations"))
    story.append(PageBreak())

    chapter("Day by day","Your itinerary")
    for day in data["itinerary"]["days"]:
        story.append(p(f"Day {day['day']} · {day.get('calendar_date') or 'Date to confirm'}","BookKicker"))
        for stop in day["stops"]:
            story.append(p(f"{stop['start_time']}–{stop.get('end_time') or ''}   {stop['title']}"))
            story.append(p(f"{stop.get('location') or brief['destination']} · {money(stop['est_cost_inr'])} / guest · {stop.get('notes') or 'Opening hours and practical details are unverified.'}","BookSmall"))
        story.append(Spacer(1,3*mm))
    story.append(edit_link("Edit your dated itinerary","trip/"+data["trip_id"]))
    story.append(PageBreak())

    chapter("Stay a little longer","Your selected accommodation")
    stay=data["stay"]
    if stay:
        story.append(p(stay["name"],"BookHeading"))
        table([["Location",stay["location"]],["Nights",str(stay["nights"])],["Indicative nightly room rate",money(stay["price_per_night_inr"])],["Selection status",stay["status"]]])
        if stay.get("source_url"):
            story.append(p("Research source: " + stay["source_url"], "BookSmall"))
        story.append(p("The estimate assumes one room for all nights. Room occupancy, child policies, taxes, check-in times and cancellation terms require confirmation. A room in one city does not confirm accommodation in every city on a regional route."))
    else:
        story.append(p("No accommodation has been selected. Room costs are excluded until a supported stay is chosen."))
    story.append(edit_link("Change your stay with Voyara AI","hotels"))
    story.append(PageBreak())

    chapter("The way there","Flights & transport")
    flight=data["flight"]
    if flight:
        table([["Route",flight["origin"]+" to "+flight["location"]],["Requested date",flight.get("date") or brief["start_date"]],
               ["Operator",flight["name"]],["Indicative fare per guest",money(flight["price_inr"])],["Status","Selected sample outbound route; no ticket issued"]])
    else:
        story.append(p("No flight has been selected. Airfare is not included in this estimate."))
    story.append(p("Return flights, local transfers, baggage, airport buffers and supplier taxes are unverified. No flight number, departure time, ticket or reservation is invented."))
    if data["route"]:
        story.append(p("Places appearing in selected activities: "+" → ".join(data["route"])))
    story.append(edit_link("Choose sample flights for this trip","flights"))
    story.append(PageBreak())

    chapter("Make room for discovery","Experiences & local food")
    for day in data["itinerary"]["days"]:
        for stop in day["stops"]:
            if stop["kind"] in {"attraction","food"}:
                story.append(p(stop["title"],"BookKicker"))
                story.append(p(f"Day {day['day']} · {stop.get('location') or brief['destination']} · {money(stop['est_cost_inr'])} / guest"))
    if data["guide"]:
        story.append(p(data["guide"]["cuisine"]))
    story.append(edit_link("Change tours & experiences","tours"))
    story.append(PageBreak())

    chapter("Know what is included","Your indicative trip budget")
    table([[line["category"].title(),money(line["amount_inr"])] for line in data["budget"]["lines"]])
    story.append(p(money(data["budget"]["total_inr"])+(" total" if data["budget"].get("costs_complete", True) else " known subtotal; total unknown"),"BookPrice"))
    story.append(p("Confirmed budget limit: "+money(brief["budget_total_inr"])))
    story.append(p("Remaining against your budget: "+money(brief["budget_total_inr"]-data["budget"]["total_inr"]) if data["budget"].get("costs_complete", True) else "Budget fit cannot be assessed until missing supplier quotes are supplied."))
    for warning in data["budget"]["warnings"] + data["itinerary"]["assumptions"]:
        story.append(p(warning,"BookSmall"))
    story.append(p("All figures describe an indicative demo draft, not a supplier quotation or confirmed holiday price. Changing choices online creates a new plan/version; this downloaded document remains unchanged."))
    story.append(edit_link("Review & change your selections","travel-book/"+data["trip_id"]))
    story.append(PageBreak())

    chapter("Take the details with you","Your trip, your next chapter")
    story.append(p(f"Prepared for {data['traveler']} · plan version {data['version']}"))
    if data["guide"]:
        story.append(p(data["guide"]["packing"]))
    story.append(p(data["notice"]))
    story.append(p("This book contains no tickets, vouchers or supplier confirmation numbers. Sign in to the owning account to use its edit links. A QR code is a navigation link, not a public sharing permission."))
    url=base_url.rstrip('/')+'/#travel-book/'+data["trip_id"]
    qr=QrCodeWidget(url)
    bounds=qr.getBounds(); scale=65/(bounds[2]-bounds[0])
    drawing=Drawing(65,65,transform=[scale,0,0,scale,0,0]); drawing.add(qr)
    story.extend([drawing,Spacer(1,5*mm),edit_link("Open your private online Travel Book","travel-book/"+data["trip_id"]),Spacer(1,7*mm)])
    story.append(p(data["photo_attribution"],"BookSmall"))
    story.append(p("Destination information is editorial demo guidance. Check official sources and suppliers for current weather, entry requirements, access, transport and operating conditions.","BookSmall"))
    def page_frame(canvas,doc):
        canvas.saveState()
        w,h=doc.pagesize
        canvas.setFillColor(navy); canvas.rect(0,h-20*mm,w,20*mm,fill=1,stroke=0)
        canvas.setFillColor(colors.white); canvas.setFont("Helvetica-Bold",16); canvas.drawString(18*mm,h-13*mm,"VOYARA")
        canvas.setFont("Helvetica",8); canvas.drawRightString(w-18*mm,h-12*mm,"TOURS · TRAVELS · YOUR PERSONAL TRAVEL BOOK")
        canvas.setStrokeColor(saffron); canvas.setLineWidth(3); canvas.line(18*mm,17*mm,w-18*mm,17*mm)
        canvas.setFillColor(navy); canvas.setFont("Helvetica",8)
        canvas.drawString(18*mm,11*mm,"DRAFT · SYNTHETIC HACKATHON INVENTORY")
        canvas.drawRightString(w-18*mm,11*mm,f"Voyara · {doc.page}")
        canvas.restoreState()
    document.build(story,onFirstPage=page_frame,onLaterPages=page_frame)
    return out.getvalue()
