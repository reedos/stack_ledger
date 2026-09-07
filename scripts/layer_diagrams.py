"""Original explanatory diagrams; conceptual relationships, never measured topology."""
from html import escape as e

# Position, short label, pictogram, description. Counts of drawn objects are decorative.
DIAGRAMS={
 'energy':dict(title='From generation to dependable power.',intro='Generating electricity is the beginning. Transmission, substations and flexible resources make it usable where factories need it.',sources=['doe-demand'],nodes=[
 (55,100,'Generation','power','Nuclear, wind, solar, hydro and other generators supply electricity. Their output profiles differ.'),
 (365,100,'Transmission','grid','High-voltage lines move power between supply and demand regions.'),
 (675,100,'Substation','power','Transformers and switchgear adapt voltage and connect the local delivery system.'),
 (55,365,'Storage & flexibility','battery','Storage shifts energy in time; flexible loads can reduce demand when the system is constrained.'),
 (365,365,'Distribution','grid','Local circuits and protection equipment deliver power to customers.'),
 (675,365,'Factories & communities','factory','AI campuses, homes and industry need reliable service. Delivered MWh and connection dates matter.')],edges=[(0,1,'power'),(1,2,'power'),(2,4,'power'),(4,5,'power'),(3,4,'power')]),
 'chips':dict(title='A processor is an entire supply chain.',intro='Design becomes a physical device through fabrication, memory, packaging and test. Networking and storage silicon complete the system.',sources=['diagram-asml','diagram-factory'],nodes=[
 (55,100,'Design & EDA','chip','Architectures, processor IP and electronic design tools define the circuit and its physical layout.'),
 (365,100,'Wafer fabrication','wafer','Foundries build patterned layers through repeated manufacturing steps, including lithography and etching.'),
 (675,100,'Packaging & test','chip','Assembly connects dies and memory; testing checks that the resulting device meets requirements.'),
 (55,365,'Memory','memory','DRAM and high-bandwidth memory hold working data; NAND supports persistent storage.'),
 (365,365,'Links & controllers','network','Switches, network interfaces, DSPs and storage controllers move data between compute and storage.'),
 (675,365,'Compute system','rack','Accelerators, CPUs, memory and interconnects become a usable server or rack. A fab milestone alone is not a shipping system.')],edges=[(0,1,'data'),(1,2,'data'),(3,2,'data'),(2,5,'data'),(4,5,'data')]),
 'infrastructure':dict(title='Inside an AI factory.',intro='A conceptual campus cutaway: power and cooling sustain the racks, while storage and networks keep data moving. Software coordinates useful work.',sources=['diagram-factory'],nodes=[
 (45,90,'Power yard','power','Utility supply, transformers, switchgear and backup systems feed rack power distribution.'),
 (365,90,'Cooling plant','cooling','Heat exchangers and cooling equipment remove heat. Air, liquid and heat-rejection designs vary by site.'),
 (685,90,'External fiber','network','Campus and wide-area links connect users and other sites. Optical transport can link geographically separate facilities.'),
 (45,375,'Storage systems','storage','Persistent storage serves datasets, model files and checkpoints to compute.'),
 (365,375,'Compute halls','rack','Racks combine accelerators, CPUs and memory. Scale-up links join tightly coupled processors; scale-out networks connect servers.'),
 (685,375,'Fabric & operations','network','Switch fabrics move data; scheduling, monitoring and access controls coordinate workloads and resources.')],edges=[(0,4,'power'),(4,1,'cooling'),(2,5,'data'),(3,4,'data'),(4,5,'data')]),
 'models':dict(title='From compute to a capable service.',intro='A model is developed, evaluated and served. Tools and context can extend what it does; testing determines where it is useful.',sources=['nvidia-framework','diagram-agents'],nodes=[
 (55,100,'Data & objectives','storage','Curated data and learning objectives shape training. Data rights, coverage and quality require review.'),
 (365,100,'Training & adaptation','chip','Compute updates model parameters; further training can adapt behavior and task performance.'),
 (675,100,'Evaluation','check','Capability, reliability and safety evaluations test a particular model and deployment configuration.'),
 (55,365,'Serving / inference','rack','Serving systems execute the model for new inputs, trading off latency, throughput and cost.'),
 (365,365,'Context & tools','network','Retrieval supplies relevant information; tools let a system interact with software under defined permissions.'),
 (675,365,'Application interface','screen','An API or product delivers capabilities to a workflow. Production feedback informs further evaluation.')],edges=[(0,1,'data'),(1,2,'data'),(2,3,'data'),(3,4,'data'),(4,5,'data'),(5,2,'feedback')]),
 'applications':dict(title='The loop that turns intelligence into work.',intro='Applications connect a task to a model, tools and real-world checks. The useful output is the completed, verified result.',sources=['diagram-agents'],nodes=[
 (55,100,'A useful task','screen','A person or business defines a goal: resolve a support case, develop software, analyze evidence or perform a physical task.'),
 (365,100,'Model & workflow','chip','A workflow or agent uses model outputs to choose or execute steps within its allowed scope.'),
 (675,100,'Tools & systems','network','Software tools retrieve records or make changes. Physical applications additionally need sensors, controls and actuators.'),
 (55,365,'Human review','check','Review and permissions depend on the stakes. Escalate uncertainty and consequential actions where appropriate.'),
 (365,365,'Verified outcome','check','Tests, measurements and domain review establish whether work succeeded. A convincing answer alone is insufficient.'),
 (675,365,'Value & feedback','screen','Track quality, time, cost and real outcomes. Scientific and clinical claims need validation appropriate to their stage.')],edges=[(0,1,'data'),(1,2,'data'),(2,4,'data'),(3,4,'feedback'),(4,5,'data'),(5,1,'feedback')])
}


def icon(kind):
    shapes={
      'power':'<path d="M45 0 18 35h23L30 70 67 27H44Z"/>',
      'grid':'<path d="M40 0 15 70M40 0 65 70M27 35h26M20 52h40M10 20h60M17 10h46M40 0v70"/>',
      'battery':'<rect x="8" y="10" width="65" height="50" rx="8"/><path d="M73 26h7v18h-7M21 24v22M32 24v22M43 24v22M54 24v22"/>',
      'factory':'<path d="M4 65V24l24-14v14L52 10v14h24v41ZM13 39h10v12H13ZM35 39h10v12H35ZM57 39h10v12H57Z"/>',
      'chip':'<rect x="18" y="12" width="44" height="44" rx="5"/><rect x="28" y="22" width="24" height="24" rx="3"/><path d="M27 0v12M40 0v12M53 0v12M27 56v12M40 56v12M53 56v12M6 23h12M6 44h12M62 23h12M62 44h12"/>',
      'wafer':'<circle cx="40" cy="35" r="32"/><path d="M20 10v50M40 3v64M60 10v50M12 20h56M8 35h64M12 50h56"/>',
      'memory':'<path d="M4 12h72v42H4ZM12 54v10M24 54v10M36 54v10M48 54v10M60 54v10M72 54v10"/><rect x="12" y="23" width="17" height="20"/><rect x="40" y="23" width="25" height="20"/>',
      'network':'<rect x="25" y="0" width="30" height="20" rx="4"/><rect x="0" y="48" width="30" height="20" rx="4"/><rect x="50" y="48" width="30" height="20" rx="4"/><path d="M40 20v15H15v13M40 35h25v13"/>',
      'rack':''.join(f'<rect x="{x}" y="0" width="22" height="68" rx="3"/>'+''.join(f'<path d="M{x+4} {y}h14"/>' for y in [12,24,36,48,60]) for x in [0,29,58]),
      'storage':'<ellipse cx="40" cy="12" rx="33" ry="11"/><path d="M7 12v44c0 15 66 15 66 0V12M7 33c0 15 66 15 66 0"/>',
      'cooling':'<circle cx="40" cy="35" r="30"/><circle cx="40" cy="35" r="6"/><path d="M40 29c-23-30-35 12-6 12M46 35c36-5 4-37-9-6M40 41c-13 32 31 24 6-6"/>',
      'screen':'<rect x="3" y="5" width="74" height="48" rx="5"/><path d="M40 53v14M20 67h40M17 20l12 9-12 9M39 38h22"/>',
      'check':'<circle cx="40" cy="35" r="31"/><path d="m21 34 13 14 26-28"/>'}
    return shapes[kind]


def render_layer_diagram(layer,sources):
    d=DIAGRAMS[layer];lookup={s['id']:s for s in sources}
    paths=''
    for a,b,kind in d['edges']:
        x,y,*_=d['nodes'][a];xx,yy,*_=d['nodes'][b]
        if y==yy:
            x+=220;y+=78;yy+=78
            path=f'M{x} {y}H{xx}'
        else:
            x+=110;y+=150 if yy>y else 0;xx+=110;yy+=0 if yy>y else 150
            
            if layer=='infrastructure' and kind=='power':xx-=24
            mid=(y+yy)/2;path=f'M{x} {y}V{mid}H{xx}V{yy}'
        paths+=f'<path d="{path}" class="diagram-wire {kind}" marker-end="url(#arrow-{layer}-{kind})"/>'
    markers=''.join(f'<marker id="arrow-{layer}-{k}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 8 4 0 8Z" fill="{color}"/></marker>' for k,color in [('power','#f2c96d'),('cooling','#72d6ed'),('data','#c5f277'),('feedback','#bda4f3')])
    nodes='';details=''
    for i,(x,y,title,kind,body) in enumerate(d['nodes'],1):
        nodes+=f'<a href="#diagram-{layer}-{i}" aria-label="{i}. {e(title)}"><g class="diagram-node" transform="translate({x} {y})"><rect width="220" height="150" rx="15"/><g class="diagram-icon" transform="translate(70 20)">{icon(kind)}</g><circle cx="22" cy="22" r="16"/><text class="diagram-number" x="22" y="29" text-anchor="middle">{i}</text><text class="diagram-label" x="110" y="125" text-anchor="middle">{e(title)}</text></g></a>'
        details+=f'<article id="diagram-{layer}-{i}" class="diagram-explanation" tabindex="-1"><h3><span>{i:02}</span> {e(title)}</h3><p>{e(body)}</p></article>'
    building='<path class="factory-shell" d="M20 330 70 285H890l50 45v225H20Z"/><text class="diagram-label factory-label" x="40" y="350">DATA HALL · CONCEPTUAL CUTAWAY</text>' if layer=='infrastructure' else ''
    refs=' · '.join(f'<a href="{e(lookup[s]["url"],quote=True)}">{e(lookup[s]["publisher"])}: {e(lookup[s]["title"])} ↗</a>' for s in d['sources'])
    return f'''<section class="section layer-diagram" id="layer-diagram" data-diagram="{layer}"><div class="eyebrow">INSIDE THE LAYER / HOW IT FITS TOGETHER</div><h2>{e(d['title'])}</h2><p class="section-intro">{e(d['intro'])}</p><div class="diagram-canvas"><svg viewBox="0 0 960 570" role="group" aria-label="{e(d['title'])} Select a numbered component to read its explanation."><defs>{markers}</defs><pattern id="grid-{layer}" width="30" height="30" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#3c5240"/></pattern><rect width="960" height="570" rx="20" fill="url(#grid-{layer})"/>{building}{paths}{nodes}</svg></div><div class="diagram-key"><span class="key-power">Power / energy</span><span class="key-data">Data / process</span><span class="key-cooling">Heat removal</span><span class="key-feedback">Review / feedback</span></div><p class="chart-footnote">Original conceptual illustration, not a site plan or engineering specification. Arrows show selected relationships, not measured flows or capacity. Numbered components are explained below; select one in the diagram to jump to it.</p><div class="diagram-explanations">{details}</div><p class="chart-footnote">Technical context: {refs}</p></section>'''
