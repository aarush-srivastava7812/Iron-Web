const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const money=value=>"₹"+Number(value).toLocaleString("en-IN");

export function destinationDetails(item){
  const reasons=item.match_reasons||[];
  const fare=item.transport;
  let travel="Starting city needed — travel fares are not included in the guide price.";
  if(fare){
    travel=fare.notice;
    if(fare.costs_complete&&typeof fare.round_trip_inr==="number")travel=`${money(fare.round_trip_inr)} sample round-trip travel for ${fare.travelers} traveler${fare.travelers===1?"":"s"} from ${fare.origin}. ${fare.notice}`;
    else if(fare.origin){
      const known=(fare.legs||[]).filter(leg=>typeof leg.fare_inr==="number");
      if(known.length)travel=known.map(leg=>`${leg.direction}: ${money(leg.fare_inr)} sample fare`).join("; ")+". "+travel;
    }
  }
  const breakdown=fare?.origin&&fare.legs?.length?`<details class="journey-fare-breakdown"><summary>Travel fare breakdown</summary><ul>${fare.legs.map(leg=>`<li>${esc(leg.direction)} · ${esc(leg.origin||fare.origin)} → ${esc(leg.destination||item.name)}: ${typeof leg.fare_inr==="number"?`${money(leg.fare_inr)} for ${fare.travelers} traveler${fare.travelers===1?"":"s"}${leg.mode?` · ${esc(leg.mode)}`:""}`:"Quote needed"}</li>`).join("")}</ul><small>Lowest eligible sample fare for each leg × traveler count. Transport preferences are applied. Dates, taxes, baggage and live availability still need checking.</small></details>`:"";
  return `<div class="journey-destination-fit"><strong>Why this fits you</strong><ul>${reasons.map(reason=>`<li>${esc(reason)}</li>`).join("")||"<li>Explore this alternative; preference fit needs a closer look.</li>"}</ul><p class="journey-origin-fare">${esc(travel)}</p>${breakdown}</div>`;
}
