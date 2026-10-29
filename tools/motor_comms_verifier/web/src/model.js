import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

export async function createModel(container, onSelect) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  container.append(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.01, 50);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.HemisphereLight(0xe1edff, 0x323a44, 2.5));
  const light = new THREE.DirectionalLight(0xffffff, 3);
  light.position.set(2, 4, 3); scene.add(light);
  const robot = new THREE.Group(); robot.rotation.x = -Math.PI/2; scene.add(robot);
  const xml = new DOMParser().parseFromString(await (await fetch('/model/robot.urdf')).text(), 'application/xml');
  if (xml.querySelector('parsererror')) throw Error('Robot model could not be parsed');
  const links = {}, joints = {}, markers = [], loader = new STLLoader();
  const numbers = (value, fallback) => (value || fallback).trim().split(/\s+/).map(Number);
  function origin(group, element) {
    group.position.fromArray(numbers(element?.getAttribute('xyz'), '0 0 0'));
    const [r,p,y] = numbers(element?.getAttribute('rpy'), '0 0 0');
    group.rotation.set(r,p,y,'ZYX');
  }
  const loading = [];
  for (const link of xml.querySelectorAll('robot > link')) {
    const group = new THREE.Group(); links[link.getAttribute('name')] = group;
    for (const visual of link.querySelectorAll('visual')) {
      const meshElement = visual.querySelector('mesh'); if (!meshElement) continue;
      const visualGroup = new THREE.Group(); origin(visualGroup, visual.querySelector('origin')); group.add(visualGroup);
      const file = meshElement.getAttribute('filename').split('/').pop();
      loading.push(loader.loadAsync('/model/meshes/'+file).then(geometry => {
        const material = new THREE.MeshStandardMaterial({ color:0x8794a1, roughness:0.7, metalness:0.2 });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.scale.fromArray(numbers(meshElement.getAttribute('scale'), '1 1 1'));
        visualGroup.add(mesh);
      }));
    }
  }
  const children = new Set();
  for (const joint of xml.querySelectorAll('robot > joint')) {
    const parent = joint.querySelector('parent').getAttribute('link');
    const child = joint.querySelector('child').getAttribute('link'); children.add(child);
    const group = new THREE.Group(); origin(group, joint.querySelector('origin'));
    links[parent].add(group); group.add(links[child]);
    const marker = new THREE.Mesh(new THREE.SphereGeometry(0.019, 14, 10),
      new THREE.MeshBasicMaterial({ color:0x303944, depthTest:false }));
    // The URDF ankle pitch/roll origins coincide. Separate actuator indicators
    // vertically, raised into the shin actuator area below the knee.
    const name = joint.getAttribute('name');
    if (name.endsWith('_ankle_pitch_joint')) marker.position.z = 0.205;
    if (name.endsWith('_ankle_roll_joint')) marker.position.z = 0.135;
    marker.renderOrder=10; group.add(marker); markers.push(marker);
    joints[joint.getAttribute('name')] = { group, marker, link:links[child] };
  }
  for (const [name, group] of Object.entries(links)) if (!children.has(name)) robot.add(group);
  await Promise.all(loading);
  const box = new THREE.Box3().setFromObject(robot), center = box.getCenter(new THREE.Vector3());
  robot.position.sub(center);
  const size = box.getSize(new THREE.Vector3()).length();
  camera.position.set(size*0.8,size*0.3,size*1.6); controls.target.set(0,0,0); controls.update();
  const grid = new THREE.GridHelper(2.4, 24, 0x29343f, 0x18212a);
  grid.position.y=-box.getSize(new THREE.Vector3()).y/2-0.02; scene.add(grid);
  const resize = new ResizeObserver(() => {
    const { width, height } = container.getBoundingClientRect();
    renderer.setSize(width,height); camera.aspect=width/height; camera.updateProjectionMatrix();
  }); resize.observe(container);
  const ray = new THREE.Raycaster(); let down;
  renderer.domElement.addEventListener('pointerdown', e => { down=[e.clientX,e.clientY]; });
  renderer.domElement.addEventListener('pointerup', e => {
    if (!down || Math.hypot(e.clientX-down[0],e.clientY-down[1])>5) return;
    const rect=renderer.domElement.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1, -(e.clientY-rect.top)/rect.height*2+1),camera);
    const hit=ray.intersectObjects(markers)[0]; if (hit?.object.userData.id) onSelect(hit.object.userData.id);
  });
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene,camera); });
  const colors={idle:0x303944,waiting:0xf2c75c,ok:0x6dd9ab,error:0xf06f79};
  return { update(motors, active, selected) {
    for (const motor of Object.values(motors)) {
      const item=joints[motor.joint]; if (!item) continue;
      item.marker.userData.id=motor.id;
      const display = motor.color==='waiting' && active.includes(motor.id)
        ? 'waiting' : (motor.result || 'idle');
      const color=colors[display] ?? colors.idle;
      item.marker.material.color.setHex(color);
      // Each joint owns one fixed-size marker. Status only recolors that marker.
      item.marker.scale.setScalar(1);
      // Only this link's own meshes; never recolor all downstream joints.
      for (const visual of item.link.children) {
        if (!visual.isGroup || Object.values(joints).some(j=>j.group===visual)) continue;
        visual.traverse(obj=> { if (obj.isMesh) {
          obj.material.color.setHex(0x8794a1);
          obj.material.emissive.setHex(0);
        }});
      }
    }
  }};
}
