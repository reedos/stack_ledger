// Progressive enhancement: the complete reviewed evidence is in the built HTML.
(() => {
 const form=document.querySelector('.claims-controls');
 if(!form)return;
 const topic=document.querySelector('#claim-topic'), search=document.querySelector('#claim-search');
 const cards=[...document.querySelectorAll('.claim-card')];
 function filter(){
  const query=search.value.trim().toLocaleLowerCase();let count=0;
  for(const card of cards){card.hidden=Boolean(topic.value&&card.dataset.topic!==topic.value)||!card.textContent.toLocaleLowerCase().includes(query);if(!card.hidden)count++;}
  document.querySelector('#claims-count').textContent=`${count} of ${cards.length} claims`;
  document.querySelector('#claims-empty').hidden=count!==0;
 }
 form.hidden=false;form.addEventListener('submit',event=>event.preventDefault());
 form.addEventListener('input',filter);form.addEventListener('change',filter);
 form.addEventListener('reset',()=>setTimeout(filter,0));
 function revealAnchor(){const target=document.getElementById(location.hash.slice(1));if(target?.classList.contains('claim-card')&&target.hidden){form.reset();setTimeout(()=>target.scrollIntoView(),0);}}
 window.addEventListener('hashchange',revealAnchor);
})();
