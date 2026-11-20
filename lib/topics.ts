// Wikipedia:分類索引 / Template:Category, revision 86710543.
// The eight headings are navigation groups; Wikipedia categories form a graph.
export const CATEGORY_INDEX_URL='https://zh.wikipedia.org/wiki/Wikipedia:%E5%88%86%E9%A1%9E%E7%B4%A2%E5%BC%95';
const rows:[string,string,string][]=[
 ['culture','生活、艺术与文化','收藏|饮食=飲食|服装=服裝|交通|体育|娱乐|旅游|游戏|嗜好|工具|音乐|舞蹈|电影|戏剧|电视|摄影|绘画=繪畫|雕塑|手工艺|家庭|文明|文物|节日|虚构=虛構|符号=符號|次文化|动画=動畫|漫画'],
 ['world','世界各地','亚洲|非洲|大洋洲|北美洲|南美洲|欧洲|南极洲'],
 ['china','中华文化','中国历史|中国神话|中国音乐|中国戏曲=中国戏剧|中华民俗=中華民俗|中国文学|中文古典典籍|中国武术|中医|中国画|书法=書法|佛教|道教|生肖'],
 ['humanities','人文与社会科学','哲学|文学|艺术|语言学|历史学=歷史學|地理学|心理学|社会学|政治学=政治學|法学|军事学|传播学|新闻学|考古学|人类学|民族学|教育学=教育學|图书资讯科学=圖書資訊科學|经济学|人口学|家政学|管理学|性学=性學'],
 ['society','社会','文化|历史|语言|宗教|教育|家庭|组织|族群|经济|政治|政府|国家|传统=傳統|产业|媒体|体育|安全|法律|犯罪|奖励=獎勵|城市'],
 ['nature','自然与自然科学','生物|动物|植物|气象学|季节=季節|化学元素|矿物|地理|数学|物理学|力学=力學|化学|天文学|星座|地球科学|地质学|生物学|医学|药学=藥學|农学|资讯科学=資訊科學|系统科学=系統理論|密码学'],
 ['religion','宗教及信仰','各国宗教=各國宗教|宗教人物|宗教史|宗教建筑|宗教节日=宗教節日|宗教哲学=宗教哲學|宗教场所=宗教場所|宗教学|宗教组织=宗教組織|神祇|神话|神学=神學'],
 ['technology','工程、技术与应用科学','交通|建筑学|土木工程|电气工程=電機工程|计算机科学|机械工程|能源科学=能源|测绘学|航空航天|矿业=礦業|冶金学=冶金|印刷|化学工程|水利工程|通信技术|生物工程|材料科学=材料科學|环境科学=環境科學']
];
export const TOPIC_GROUPS=rows.map(([id,name,children])=>({id,name,children:children.split('|').map((s,i)=>{const [name,target=name]=s.split('=');return {id:`topic:${id}:${i}`,name,group:id,groupName:rows.find(x=>x[0]===id)![1],category:'Category:'+target,url:'https://zh.wikipedia.org/wiki/'+encodeURIComponent('Category:'+target)};})}));
export const TOPICS=TOPIC_GROUPS.flatMap(x=>x.children);
export const topicById=(id:string)=>TOPICS.find(t=>t.id===id);
export const topicLabel=(id:string)=>{const t=topicById(id);return t?`${t.groupName} / ${t.name}`:id;};
export const categoryKey=(s:string)=>s.replace(/^(Category|分类|分類):/i,'').replaceAll('_',' ').normalize('NFKC').trim();
export type TopicMatch={id:string;name:string;group:string;groupName:string;path:string[]};
export function directTopics(categories:string[]):TopicMatch[]{return TOPICS.filter(t=>categories.some(c=>[categoryKey(t.category),t.name].includes(categoryKey(c)))).map(t=>({id:t.id,name:t.name,group:t.group,groupName:t.groupName,path:[t.category]}));}
export function topicCategory(topics:TopicMatch[]){return [...new Set(topics.map(t=>t.name))].join('、')||'待归类';}
