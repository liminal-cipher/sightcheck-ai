import * as THREE from 'three';
import {Venue} from '../../promo-video/src/venue.js';
import {eyePosition,getObstacles} from '../../../src/model.js';
import spike from '../../../experiments/vlm-spike/model.json';
const v=new Venue(1920,1080);v.baseModel=structuredClone(spike);v.ensure();
const host=document.getElementById('hybrid-canvas');v.mount(host);
// Light-mode canvas surround only; viewport scene, materials and camera remain unchanged.
const originalClearColor=v.renderer.setClearColor.bind(v.renderer);
v.renderer.setClearColor=(color,alpha)=>originalClearColor('#f7f8f5',alpha);
const scene=v.viewer.scene;
const clamp=x=>Math.max(0,Math.min(1,x));
function ease(p){p=clamp(p);let lo=0,hi=1,t=p;for(let i=0;i<18;i++){t=(lo+hi)/2;let x=3*(1-t)**2*t*.65+3*(1-t)*t*t*.35+t**3;if(x<p)lo=t;else hi=t;}return 3*(1-t)*t*t+t**3;}
const phase=(t,a,b)=>ease((t-a)/(b-a));
const V=(x,y,z)=>new THREE.Vector3(x,y,z);
const overview={pos:V(4.2,8.6,15.6),look:V(-.3,1.2,3.2),fov:44};
const topview={pos:V(0,22,5.68),look:V(0,0,5.67),fov:45};
function mix(a,b,p){return {pos:a.pos.clone().lerp(b.pos,p),look:a.look.clone().lerp(b.look,p),fov:THREE.MathUtils.lerp(a.fov,b.fov,p)};}
const guide=new THREE.Group();scene.add(guide);
const dots=[];for(const s of v.seats){const dot=new THREE.Mesh(new THREE.SphereGeometry(s.label==='C3'?.19:.12,12,8),new THREE.MeshBasicMaterial({color:s.label==='C3'?'#ffae79':'#c7ef7b',depthTest:false,transparent:true}));dot.renderOrder=20;dot.position.set(s.x,.09,s.z);guide.add(dot);dots.push(dot);}
const stage=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([V(-4.3,.05,-1.75),V(4.3,.05,-1.75),V(4.3,.05,-.25),V(-4.3,.05,-.25)]),new THREE.LineBasicMaterial({color:'#c7ef7b',depthTest:false,transparent:true}));guide.add(stage);
const dimension=new THREE.Group();scene.add(dimension);
function line(group,pts,color){const l=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),new THREE.LineBasicMaterial({color,transparent:true,opacity:1,depthTest:false,transparent:true}));l.renderOrder=22;group.add(l);return l;}
line(dimension,[V(-4.3,.2,-.25),V(4.3,.2,-.25)],'#c7ef7b');
for(const x of [-4.3,4.3])line(dimension,[V(x,.2,-.6),V(x,.2,.1)],'#c7ef7b');
line(dimension,[V(0,0,8.8),V(0,2.4,8.8)],'#ffae79');
line(dimension,[V(-4.375,2.4,8.0575),V(-4.375,3.4,8.0575)],'#ffae79');
const rays=new THREE.Group();scene.add(rays);
const result=v.analyze(12),eye=eyePosition(v.seats[12],1.2);
const boxes=getObstacles(v.model,'theatre').map(o=>new THREE.Box3().setFromCenterAndSize(V(...o.position),V(...o.size)));
for(const s of result.samples){const p=V(s.x,s.y,s.z);const dot=new THREE.Mesh(new THREE.SphereGeometry(.034,6,4),new THREE.MeshBasicMaterial({color:s.blocked?'#ffae79':'#c7ef7b',depthTest:false,transparent:true}));dot.position.copy(p);dot.renderOrder=23;rays.add(dot);}
for(const s of result.samples.filter((s,i)=>i%26===0)){const p=V(s.x,s.y,s.z),ray=new THREE.Ray(eye.clone(),p.clone().sub(eye).normalize());let end=p;for(const box of boxes){const hit=ray.intersectBox(box,new THREE.Vector3());if(hit&&hit.distanceTo(eye)<end.distanceTo(eye))end=hit;}line(rays,[eye,end],s.blocked?'#ffae79':'#c7ef7b');}
const tex=new THREE.TextureLoader().load('assets/venue-plan.png');tex.colorSpace=THREE.SRGBColorSpace;
const plan=new THREE.Mesh(new THREE.PlaneGeometry(1000/60,930/60),new THREE.MeshBasicMaterial({map:tex,transparent:true,side:THREE.DoubleSide}));plan.rotation.x=-Math.PI/2;plan.position.set(0,0,5.6667);scene.add(plan);
const rect=[96,340,1728,620];
let lastLayout='theatre';
function renderAt(t){
 const active=t<5||(t>=9&&t<42);host.style.opacity=active?'1':'0';if(!active)return;
 const layout=t>=36&&t<42?'concert':'theatre';if(layout!==lastLayout){v.ensure(layout);lastLayout=layout;}
 v.highlight(t>=34?1:12,t>=9&&t<13?17:null);v.setRailTint(0);v.setTowerRise(1);
 plan.visible=t>=18&&t<28;guide.visible=t>=19&&t<30;dimension.visible=t>=23&&t<29.8;rays.visible=(t>=14.3&&t<18)||(t>=31&&t<34);
 v.viewer.root.visible=!(t>=18&&t<26.3);
 let views=[];
 if(t<5||t>=9&&t<13){const y=t<5?428:370;const q=phase(t,t<5?.5:9,t<5?4:12.5);views=[{rect:[96,y,850,478],pose:v.seatPose(12,{yaw:(1-q)*.06})},{rect:[974,y,850,478],pose:v.seatPose(17,{yaw:(1-q)*.06})}];}
 else if(t<18){let p=phase(t,13.5,17.2);views=[{rect,pose:mix(v.seatPose(12),overview,p)}];v.setRailTint(phase(t,14.5,15));}
 else if(t<34){
  const tilt=phase(t,23.5,27);let pose=mix(topview,overview,tilt);
  plan.material.opacity=1-phase(t,26.3,27.4);
  dots.forEach((d,i)=>{d.material.color.set(t<26?'#467a1b':(i===12?'#ffae79':'#c7ef7b'));d.position.y=.09+v.seats[i].floor*phase(t,24.2,26.2);d.scale.setScalar(.1+.9*phase(t,19+i*.018,19.5+i*.018));});
  const land=phase(t,26.3,27.7);v.viewer.root.scale.y=Math.max(.001,land);
  pose=mix(pose,v.seatPose(12),phase(t,28.6,31));
  views=[{rect,pose}];if(t>=31)v.setRailTint(phase(t,31,31.7));
 }else {v.viewer.root.scale.y=1;v.setTowerRise(phase(t,36,37.6));views=[{rect,pose:v.seatPose(1,{yaw:(1-phase(t,34,35.5))*.05})}];}
 if(t<18||t>=34)v.viewer.root.scale.y=1;
 v.render(views);
}
window.renderHybrid=renderAt;window.addEventListener('hf-seek',e=>renderAt(e.detail.time));renderAt(window.__hfThreeTime||0);
