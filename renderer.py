#! /usr/bin/env python

import Image, math, random, collections, json, os

# ---

SPRITE_PATH = '/Base/Sprites%s'
SCRIPT_PATH = './%s'

BLOCK_SIZE = 8

# ---

def hexcolor(pixel):
	def hex2(number):
		h = hex(number)[2:]
		if len(h) == 1:
			h = '0'+h
		return h
	return hex2(pixel[0]) + hex2(pixel[1]) + hex2(pixel[2])

# ---

class BlockCache(object):
	def __init__(self):
		self.sheet = Image.open(SPRITE_PATH % '/world.png')
		with file(SCRIPT_PATH % '/blocks.json') as f:
			self.guide = json.loads(f.read())
		
		self.blocks_name = {}
		self.blocks_color = {}
		
		for info in self.guide:
			# load blocks
			blocks = []
			for pos in info['blocks']:
				x, y = pos
				box = tuple([n*BLOCK_SIZE for n in [x, y, x+1, y+1]])
				image = self.sheet.transform((BLOCK_SIZE, BLOCK_SIZE), Image.EXTENT, box)
				block = (info['name'].encode('ascii'), info['type'].encode('ascii'), image)
				blocks.append(block)
			
			if info['type'] == 'empty':
				blocks.append(('empty', 'empty', None))
			
			# sort
			self.blocks_name[info['name']] = blocks
			for pixel in info['colors']:
				color = hexcolor(pixel)
				self.blocks_color[color] = blocks
		
		# rotate spikes
		spikes = ['spikes', 'spikes_dirt', 'spikes_castle']
		angles = {'t':0, 'l':90, 'b':180, 'r':270}
		for name in spikes:
			image = self.by_name(name)[2]
			for post, angle in angles.iteritems():
				new = image.rotate(angle)
				self.blocks_name['%s_%s' % (name, post)] = [new]
	
	def by_name(self, name, i=None):
		return self._block(self.blocks_name[name], i)
	
	def by_color(self, pixel, i=None):
		color = hexcolor(pixel)
		return self._block(self.blocks_color[color], i)
	
	def _block(self, blocks, i):
		if i is not None:
			return blocks[i]
		return blocks[random.randrange(len(blocks))]

# ---

class Block(object):
	@classmethod
	def load_cache(cls):
		cls.cache = BlockCache()
	
	def __init__(self, map, pos, pixel):
		self.map = map
		self.pos = pos
		self.x, self.y = pos
		self.pixel = pixel
		self.name, self.type, self.image = self.cache.by_color(pixel)
		self.borders = None
		self.borders_c = None
		self.hidden = None
	
	def get_borders(self):
		if not self.borders:
			self.borders = [
				self.map[self.x-1, self.y-1],	#tl
				self.map[self.x, self.y-1],		#t
				self.map[self.x+1, self.y-1],	#tr
				self.map[self.x+1, self.y],		#r
				self.map[self.x+1, self.y+1],	#br
				self.map[self.x, self.y+1],		#b
				self.map[self.x-1, self.y+1],	#bl
				self.map[self.x-1, self.y],		#l
			]
		return self.borders
	
	def get_borders_counter(self):
		if not self.borders_c:
			temp = [block.type for block in self.get_borders()]
			self.borders_c = collections.Counter(temp)
		return self.borders_c
	
	def is_hidden(self):
		if self.hidden is None:
			self.hidden = self.get_borders_counter()['solid'] == 8
		return self.hidden

# ---

class BlockSet(object):
	def __init__(self, size):
		self.size = size
		self.w, self.h = size
		self.blocks = []
		self.blocks_rows = [[] for i in range(size[1])]
		self.blocks_cols = [[] for i in range(size[0])]
	
	def add(self, block):
		self.blocks.append(block)
		self.blocks_rows[block.y].append(block)
		self.blocks_cols[block.x].append(block)
	
	def get_all(self):
		return self.blocks
	
	def get_row(self, y):
		return self.blocks_rows[y]
	
	def get_col(self, x):
		return self.blocks_cols[x]
		

class BlockMap(object):
	def __init__(self, size):
		self.size = size
		self.w, self.h = size
		
		self.all = BlockSet(self.size)
		self.by_type = {}
		self.empty = BlockSet(self.size)
	
	def __getitem__(self, key):
		if type(key) is str:
			if key not in self.by_type: return self.empty
			return self.by_type[key]
		pos = key
		if pos[0] < 0 or pos[0] >= self.w or pos[1] < 0 or pos[1] >= self.h:
			return Block(self, pos, [100, 113, 96])
		return self.all.get_row(pos[1])[pos[0]]
	
	def __setitem__(self, pos, pixel):
		if pos[0] < 0 or pos[0] >= self.w or pos[1] < 0 or pos[1] >= self.h:
			raise TypeError('index out of range')
		
		block = Block(self, pos, pixel)
		
		self.all.add(block)
		
		if block.type not in self.by_type:
			self.by_type[block.type] = BlockSet(self.size)
		
		self.by_type[block.type].add(block)

# ---

class Renderer(object):
	def __init__(self, source):
		self.source = Image.open(source).convert('RGBA')
		self.output = Image.new('RGBA', tuple([n*BLOCK_SIZE for n in self.source.size]))
		self.map = BlockMap(self.source.size)
	
	def process(self):
		pixels = self.source.load()
		
		for y in xrange(self.source.size[1]):
			for x in xrange(self.source.size[0]):
				try:
					self.map[x,y] = pixels[x,y]
				except KeyError:
					print 'missing:', (x,y), pixels[x,y]
					self.map[x,y] = (0, 0, 0)
		
		return self
	
	def render(self, shadows=True, background=True, bdelta=0):
		if background:
			# background gradient
			bg = Image.open(SCRIPT_PATH % '/bg_gradient.png').convert('RGBA').resize(self.output.size)
			self.output.paste(bg, (0, 0, self.output.size[0], self.output.size[1]))
		
			background_y = self.output.size[1]/2 + 70 + bdelta
		
			# plains
			im = Image.open(SPRITE_PATH % '/Back/BackgroundPlains.png').convert('RGBA')
			pos_y = background_y - im.size[1]
			for i in xrange(int(math.ceil(self.output.size[0]/float(im.size[0])))):
				self.output.paste(im, (i*im.size[0], pos_y), im)
		
			# trees
			im = Image.open(SPRITE_PATH % '/Back/BackgroundTrees.png').convert('RGBA')
			pos_y = background_y - im.size[1]
			for i in xrange(int(math.ceil(self.output.size[0]/float(im.size[0])))):
				self.output.paste(im, (i*im.size[0], pos_y), im)
		
			# grass + castle
			im = Image.open(SPRITE_PATH % '/Back/BackgroundCastle.png').convert('RGBA')
			pos_y = background_y - im.size[1]
			for i in xrange(int(math.ceil(self.output.size[0]/float(im.size[0])))):
				self.output.paste(im, (i*im.size[0], pos_y), im)
		
			# green background
			im_under = im.crop((im.size[0]-1, im.size[1]-1, im.size[0], im.size[1]))
			im_under.load()
			im_under = im_under.resize((self.output.size[0], self.output.size[1]-im.size[1]))
			self.output.paste(im_under, (0, im.size[1]+pos_y))
		
			# clouds
			clouds = []
			for i in range(1, 5):
				cloud = Image.open(SPRITE_PATH % '/Back/cloud%d.png' % i).convert('RGBA')
				r,g,b,a = cloud.split()
				a = Image.blend(Image.new('L', a.size, 0), a.convert('L'), 0.15)
				cloud = Image.new('RGBA', cloud.size, (255,255,255,0))
				detail = Image.merge('RGB', (r,g,b))
				cloud.paste(detail, (0,0), a)
				clouds.append(cloud)
			# top clouds
			for i in range(self.output.size[0]/80):
				cloud = clouds[random.randrange(len(clouds))]
				r,g,b,a = cloud.split()
				cloud = Image.merge('RGB', (r,g,b))
				x = random.randrange(self.output.size[0]+200)
				y = random.randrange(100)
				self.output.paste(cloud, (x-100, background_y+y-600), a)
			# bottom clouds
			for i in range(self.output.size[0]/50):
				cloud = clouds[random.randrange(len(clouds))]
				r,g,b,a = cloud.resize((cloud.size[0]*2, cloud.size[1]*2)).split()
				a = Image.blend(Image.new('L', a.size, 0), a.convert('L'), 0.4)
				cloud = Image.merge('RGB', (r,g,b))
				x = random.randrange(self.output.size[0]+200)
				y = random.randrange(300)
				self.output.paste(cloud, (x-100, background_y+y-350), a)
		
		shadow = Image.new('RGBA', (BLOCK_SIZE, BLOCK_SIZE), (0x26, 0x0d, 0x0d, 0xFF))
		
		gradient_t = Image.open(SCRIPT_PATH % '/gradient.png').convert('RGBA')
		gradient_l = gradient_t.rotate(90)
		gradient_b = gradient_l.rotate(90)
		gradient_r = gradient_b.rotate(90)
		
		#gradient_tr = Image.open('gradient-diagonal.png').convert('RGBA')
		#gradient_tl = gradient_tr.rotate(90)
		#gradient_bl = gradient_tl.rotate(90)
		#gradient_br = gradient_bl.rotate(90)
		
		def mix(bottom, top):
			r, g, b, a = top.split()
			top = Image.merge('RGB', (r,g,b))
			mask = Image.merge('L', (a,))
			im = bottom.copy()
			im.paste(top, (0,0), mask)
			return im
		
		# background blocks
		for block in self.map['background'].get_all():
			self.output.paste(block.image, tuple([n*BLOCK_SIZE for n in block.pos]), block.image)
		
		# spikes
		for block in self.map['spikes'].get_all():
			# background
			if block.name == 'spikes_dirt':
				bkg = Block.cache.by_name('dirt_background')[2]
			elif block.name == 'spikes_castle':
				bkg = Block.cache.by_name('castle_wall')[2]
			if block.name != 'spikes':
				self.output.paste(bkg, tuple([n*BLOCK_SIZE for n in block.pos]), bkg)
			
			draw_block = block.image
			b = block.get_borders()
			# orientation
			if b[5].type == 'solid':
				draw_block = Block.cache.by_name('%s_%s' % (block.name, 't'))
			elif b[1].type == 'solid':
				draw_block = Block.cache.by_name('%s_%s' % (block.name, 'b'))
			elif b[3].type == 'solid':
				draw_block = Block.cache.by_name('%s_%s' % (block.name, 'l'))
			elif b[7].type == 'solid':
				draw_block = Block.cache.by_name('%s_%s' % (block.name, 'r'))
			
			r,g,b,a = draw_block.split()
			detail = Image.merge('RGB', (r,g,b))
			
			# change to allow depth shadow
			block.type = 'background'
			
			self.output.paste(detail, tuple([n*BLOCK_SIZE for n in block.pos]), a)
		
		# solid blocks
		for block in self.map['solid'].get_all():
			draw_block = block.image
			borders = block.get_borders()
			
			if block.name == 'castle':
				if borders[1].name == 'castle_wall':
					draw_block = Block.cache.by_name('castle_floor')[2]
				elif borders[5].name == 'castle_wall':
					draw_block = Block.cache.by_name('castle_roof')[2]
				elif borders[5].name.endswith('door'):
					draw_block = Block.cache.by_name('castle_door')[2]
			
			# fog
			if shadows:
				if block.is_hidden():
					draw_block = shadow
				else:
					if borders[1].is_hidden():
						draw_block = mix(draw_block, gradient_b)
					if borders[3].is_hidden():
						draw_block = mix(draw_block, gradient_l)
					if borders[5].is_hidden():
						draw_block = mix(draw_block, gradient_t)
					if borders[7].is_hidden():
						draw_block = mix(draw_block, gradient_r)
			
			self.output.paste(draw_block, tuple([n*BLOCK_SIZE for n in block.pos]), block.image)
			
			# background depth
			depth = {'gradient_t':1, 'gradient_r':3, 'gradient_b':5, 'gradient_l':7}
			for name, side in depth.iteritems():
				if borders[side].type != 'background' or borders[side].name == 'spikes':
					continue
				draw_block = locals()[name]
				r,g,b,a = draw_block.split()
				detail = Image.merge('RGB', (r,g,b))
				self.output.paste(detail, tuple([n*BLOCK_SIZE for n in borders[side].pos]), a)
		
		# trees
		im = Image.open(SPRITE_PATH % '/Trees/pine.png').convert('RGBA')
		treetops = []
		for i in range(4):
			treetop = im.transform((38, 38), Image.EXTENT, (0, 38*i, 38, 38*(i+1)))
			treetops.append(treetop)
		branches = []
		for i in range(4, 7):
			branch = im.transform((38, 38), Image.EXTENT, (0, 38*i, 38, 38*(i+1)))
			branches.append(branch)
		# draw
		for x in xrange(self.map.w):
			height = 0
			blocks = []
			for block in self.map['tree'].get_col(x):
				pos = tuple([n*BLOCK_SIZE for n in block.pos])
				borders = block.get_borders()
				
				blocks.append(pos)
				height += 1
				
				draw_block = block.image
				
				# end of tree
				if borders[5].type != 'tree':
					# treetop
					if height > 3:
						treetop = treetops[random.randrange(len(treetops))]
						self.output.paste(treetop, (blocks[0][0]-15, blocks[0][1]-23), treetop)
					
					# branches  and random.random()>.8
					if height > 5:
						for i in range(2, height-2):
							if random.random() < .7: continue
							branch = branches[random.randrange(len(branches))]
							self.output.paste(branch, (blocks[i][0]-19, blocks[i][1]-12), branch)
					
					#stump
					draw_block = Block.cache.by_name('tree_stump')[2]
					
					# reset
					height = 0
					blocks = []
				
				self.output.paste(draw_block, pos, draw_block)
		
		# spawn points
		blue = Image.open(SPRITE_PATH % '/tent1.png').convert('RGBA').transform((32, 32), Image.EXTENT, (0, 0, 32, 32))
		red = Image.open(SPRITE_PATH % '/tent2.png').convert('RGBA').transform((32, 32), Image.EXTENT, (0, 0, 32, 32))
		for block in self.map['blue_spawn'].get_all():
			pos = tuple([n*BLOCK_SIZE for n in block.pos])
			self.output.paste(blue, (pos[0]-16, pos[1]-16), blue)
		for block in self.map['red_spawn'].get_all():
			pos = tuple([n*BLOCK_SIZE for n in block.pos])
			self.output.paste(red, (pos[0]-16, pos[1]-16), red)
		
		return self.output

# ---

if __name__ == '__main__':
	import argparse
	
	# Args
	parser = argparse.ArgumentParser(description='Render a blueprint map for the game King Arthurs Gold.')
	
	parser.add_argument('-s', help='Disable shadow layer.', action='store_false', default=True)
	parser.add_argument('-b', help='Disable background layer.', action='store_false', default=True)
	parser.add_argument('-bdelta', '--bdelta', help='Shift the background layer X pixels. up=-X; down=+X. Default: 0', metavar='X', type=int, default=0)
	parser.add_argument('-path', '--path', help='Path to KAG installation. (no trailing slash). Default: .', metavar='PATH', type=str, default='.')
	parser.add_argument('-f', '--f', help='Format for the rendered map (JPEG, PNG). Default: PNG', metavar='FORMAT', default='PNG')
	parser.add_argument('-o', '--o', help='Path to save rendered map at. Default: source + ".out"', metavar='PATH', default=None)
	
	parser.add_argument('source', help='Pixel map.')
	
	args = parser.parse_args()
	# ---
	
	SPRITE_PATH = os.path.abspath(args.path) + SPRITE_PATH
	SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__)) + '%s'
	
	if args.o is None:
		args.o = os.path.abspath(args.source) + '.out'
	
	if not os.path.exists(SPRITE_PATH % ''):
		print 'ERROR: Invalid PATH to KAG installation.'
		parser.print_usage()
		exit(1)
	
	import time
	start = time.time()
	
	Block.load_cache()
	
	Renderer(args.source).process().render(shadows=args.s, background=args.b, bdelta=args.bdelta).save(args.o, args.f)
	
	print time.time() - start
	print args.o

# ---
# END
