import SCons as scons
import SCons.Environment as e
import os
import sys
import sfle
import time

class IO:

    def __init__( self, srs, tgt, ssrs, stgt, kwargs = None ):
        self.__inpf = ( s.path for s in srs )
        self.__outf = ( o.path for o in tgt )
        self.inpf = [ s.path for s in srs ]
        self.outf = [ o.path for o in tgt ]
        self.sinpf = [ s.path for s in ssrs ]
        self.soutf = [ o.path for o in stgt ]
        self.args = kwargs
        self.opened = []

    def open( self, fn ):
        return open( fn )

    @property
    def inp_open(self):
        try:
            inp = self.open( self.__inpf.next() )
        except StopIteration:
            return None
        self.opened.append( inp )
        return inp       

    @property
    def inp(self):
        inp = self.inp_open
        if inp == None:
            return None
        return (l for l in inp)
    
    @property
    def inp_all(self):
        import itertools
        inps = []
        while True:
            nf = self.inp
            if nf:
                inps.append(nf)
            else:
                break
        return itertools.chain(*inps)

    @property
    def out_open(self,mode='w'):
        try:
            out = open( self.__outf.next(), mode )
        except StopIteration:
            return None
        self.opened.append( out )
        return out 
 

    def __inp_tab__( self, it, comment = None, 
                     strip = True, strip_chars = None,
                     split = True, tok = '\t' ):
        strip_f = lambda x: x.strip(strip_chars) if strip else x
        split_f = lambda x: x.split(tok) if split else x
        return (split_f(ll) for ll in 
                    (strip_f(l) for l in it)
                        if ll and ll[0] != comment)
 
    def __inp_dict__( self, it, col_key = 0, col_val = 1, 
                      key_join = '_', val_join = '\t',
                      comment = None,
                      strip = True, strip_chars = None,
                      split = True, tok = '\t' ):
        k = [col_key] if isinstance(col_key, int) else col_key
        v = [col_val] if isinstance(col_val, int) else col_val
        return dict([(  key_join.join([dd for i,dd in enumerate(d) if i in k]),
                        val_join.join([dd for j,dd in enumerate(d) if j in v])  ) 
                            for d in it])

    def inp_tab( self, all_inp = False, comment = None, 
                 strip = True, strip_chars = None,
                 split = True, tok = '\t' ):
        it = self.inp_all if all_inp else self.inp
        return self.__inp_tab__( it, comment, strip, strip_chars, split, tok ) 
    
    def inp_dict( self, col_key = 0, col_val = 1, 
                  key_join = '_', val_join = '\t',
                  comment = None,
                  strip = True, strip_chars = None,
                  split = True, tok = '\t' ):
        data = self.inp_tab( comment, strip, strip_chars, split, tok )
        return self.__inp_dict__( data, col_key, col_val, key_join, val_join, 
                                  comment, strip, strip_chars, split, tok )

    def out_tab( self, buf, sep = '\t' ):
        with self.out_open as outf: 
            for b in buf:
                if isinstance(b, basestring):
                    outf.write( b + "\n" )
                else:
                    outf.write( sep.join( b ) + "\n" )

    def __del__( self ):
        for o in self.opened:
            o.close()

#@singleton
class ooSfle:
    def __init__( self, le = None, path = [], fileDirInput = "input", fileDirOutput = ".", fileDirTmp = ".", fileDirSrc = "src" ):
        self.lenv = le if le else e.Environment()
        for p in path:
            self.lenv.PrependENVPath('PATH', p)
        self.fileDirInput = fileDirInput
        self.fileDirOutput = fileDirOutput
        self.fileDirTmp = fileDirTmp
        self.fileDirSrc = fileDirSrc
        import subprocess as sb

    def rebase( self, pPath, strFrom = None, strTo = "" ):
        return sfle.rebase( pPath, strFrom, strTo )

    def fin( self, fn ):
        return str(self.lenv.File( sfle.d( self.fileDirInput, fn )) )
    
    def fout( self, fn ):
        return str(self.lenv.File( sfle.d( self.fileDirOutput, fn )))
    
    def fsrc( self, fn ):
        return self.lenv.File( sfle.d( self.fileDirSrc, fn )).path

    def ftmp( self, fn ):
        return str(self.lenv.File( sfle.d( self.fileDirTmp, fn ) ))

    def f(  self, srs, tgt, func, srs_dep = None, tgt_dep = None, 
            __kwargs_dict__ = None, fname = None, attempts = 1, **kwargs ):
        if srs_dep is None: srs_dep = []
        if tgt_dep is None: tgt_dep = []
        if srs is None:
            nsrs = []
        else:
            nsrs = [srs] if isinstance( srs, str) else srs
        if tgt is None:
            ntgt = []
        else:
            ntgt = [tgt] if isinstance( tgt, str) else tgt
        nsrs_dep = [srs_dep] if isinstance( srs_dep, str) else srs_dep
        ntgt_dep = [tgt_dep] if isinstance( tgt_dep, str) else tgt_dep
        att = attempts 
 
        def _f_( target, source, env ):
            lsrs, ltgt = len(nsrs), len(ntgt)
            lio = IO(   srs = source[:lsrs], tgt = target[:ltgt],
                        ssrs = source[lsrs:], stgt = target[ltgt:],
                        kwargs = __kwargs_dict__ if __kwargs_dict__ else kwargs )
            ret = 1
            attempts = att
            while ret and attempts:
                ret = func( lio )
                attempts -= 1
                if attempts:
                    time.sleep(2**(att-attempts))
            return ret      
 
        _f_.__name__ = "oo scons: "+(fname if fname else func.func_name)
        return self.lenv.Command( ntgt + ntgt_dep, nsrs + nsrs_dep, _f_ )


    def pipe( self, fr, to, excmd, deps = [], __kwargs_dict__ = None, **kwargs ):
        import subprocess as sb
        def _extex_( io ):
            cmd = [str(excmd)]
            for k,v in kwargs.items():
                cmd += ["-"+k if len(k) == 1 else "--"+k] + [str(v)] if v else []
            sb.call( cmd, stdout = io.out_open, stdin = io.inp_open )
        self.f( fr, to, _extex_, deps = deps, fname = str(excmd), __kwargs_dict__ = kwargs )

    def ext( self, fr, to, excmd, outpipe = True, verbose = False, attempts = 1, deps = None, out_deps = None, __kwargs_dict__ = None, args = None, long_args = '--', **kwargs ):
        import subprocess as sb
        if __kwargs_dict__ and kwargs:
            kwargs.update( __kwargs_dict__ )
        elif __kwargs_dict__:
            kwargs = __kwargs_dict__
        def _ext_( io ):
            cmd = [str(excmd)]
            for k,v in kwargs.items():
                if not k:
                    cmd += [str(v)]
                elif len(k) == 1:
                    cmd += ["-"+k] + ([str(v)] if v else [])
                elif len(k) > 1:
                    cmd += [long_args+k] + ([str(v)] if v else [])
            if args:
               for a in args:
                   cmd += [a[0],a[1]] if type(a) in [list,tuple] else [a]
            cmd += io.inpf
            if not outpipe:
                cmd += io.outf
            if verbose:
                sys.stdout.write("oo scons ext: " + " ".join(cmd) + (' > '+ io.outf[0] if outpipe and io.outf else '')+"\n")
            if outpipe:
                return sb.call( cmd, stdout = io.out_open )
            else:
                return sb.call( cmd )
        return self.f( fr, to, _ext_, srs_dep = deps, tgt_dep = out_deps, attempts = attempts, fname = str(excmd), __kwargs_dict__ = kwargs )


    def cat( self, srs, tgt, srs_dep = [], tgt_dep = [], **kwargs ):
        def _cat_( io ):
            inp = io.inp_tab(all_inp = True)
            io.out_tab( inp )
        return self.f( srs, tgt, _cat_, srs_dep, tgt_dep, __kwargs_dict__ = kwargs, fname = "registered cat" )

    def cut( self, srs, tgt, srs_dep = [], tgt_dep = [], **kwargs ):
        def _cut_( io ):
            inp = io.inp_tab(all_inp = True)
            fs = [int(a) for a in io.args['f'].split(',')]
            out = [l for i,l in enumerate(zip(*inp)) if i+1 in fs]
            out = zip(*out)
            io.out_tab( out )
        return self.f( srs, tgt, _cut_, srs_dep, tgt_dep, __kwargs_dict__ = kwargs, fname = "registered cut" )

    # zip support need to be added
    def extract( self, srs, tgt, files2extract = None  ):
        if type(files2extract) is str:
            files2extract = [files2extract]
        assert( type(srs) is list and len(srs) == 1 or type(srs) is str)
        assert( type(tgt) is list and len(tgt) == 1 or type(tgt) is str)
        def __extract__( io ):
            import tarfile
            f = io.inpf[0]
            if tarfile.is_tarfile(f):
                with open(io.outf[0],'w') as outf:
                    with tarfile.open( f ) as tf:
                        membs = tf.getmembers()
                        for m in membs:
                            if not files2extract or m in files2extract:
                                outf.writelines( tf.extractfile(m).readlines() )
        return self.f( srs, tgt, __extract__ ) 
            

    def download( self, url, tgt, attempts = 1, **kwargs ):
        if not url:
            url = re.sub( r'^.*\/', "", strURL )
        kwargs['url'] = url
        kwargs['o'] = tgt
        kwargs['z'] = tgt
        return self.ext( None, None, "curl", verbose = True, outpipe = False, attempts = attempts, out_deps = tgt, __kwargs_dict__=kwargs) 

    def blastn( self, srs, tgt, srs_dep = None, tgt_dep = None, makedb = True,**kwargs ):
        #inpf = srs if type(srs) is str else srs[0]
        assert( type(srs) is list and len(srs) == 2 )
	dbfs = [srs[1]+d for d in ['.nhr','.nin','.nsq']]
        if makedb:
            self.ext( [], [], 'makeblastdb', verbose = True, 
                      deps = [srs[1]], out_deps = dbfs, 
                      args = [('-dbtype','nucl'),('-in',srs[1]),('-out',srs[1])], 
                      outpipe = False, long_args = '-' )
	self.ext( [], tgt, 'blastn', deps = dbfs+[srs[0]], verbose = True, 
                  args = [('-query',srs[0]),('-db',srs[1])], long_args = '-',
                  __kwargs_dict__ = kwargs )
    
    def makeblastndb( self, srs, tgt = None, srs_dep = None, tgt_dep = None, **kwargs ):
        #inpf = srs if type(srs) is str else srs[0]
        tgt = srs if tgt is None else tgt
	dbfs = [tgt+d for d in ['.nhr','.nin','.nsq']]
        self.ext( [], [], 'makeblastdb', verbose = True, 
                  deps = [srs], out_deps = dbfs, 
                  args = [('-dbtype','nucl'),('-in',srs),('-out',tgt)], 
                  outpipe = False, long_args = '-' )

    def makeblastpdb( self, srs, tgt = None, srs_dep = None, tgt_dep = None, **kwargs ):
        #inpf = srs if type(srs) is str else srs[0]
        tgt = srs 
	dbfs = [tgt+d for d in ['.phr','.pin','.psq']]
        print dbfs
        self.ext( [], [], 'makeblastdb', verbose = True, 
                  deps = [srs], out_deps = dbfs, 
                  args = [('-dbtype','prot'),('-in',srs),('-out',tgt)], 
                  outpipe = False, long_args = '-' )

    def blastp( self, srs, tgt, srs_dep = None, tgt_dep = None, makedb = True, **kwargs ):
        #inpf = srs if type(srs) is str else srs[0]
        assert( type(srs) is list and len(srs) == 2 )
	dbfs = [srs[1]+d for d in ['.phr','.pin','.psq']]
        """"
        if makedb:
            self.ext( [], [], 'makeblastdb', verbose = True, 
                      deps = [srs[1]], out_deps = dbfs, 
                      args = [('-dbtype','prot'),('-in',srs[1]),('-out',srs[1])], 
                      outpipe = False, long_args = '-' )
        """
        self.ext( [], tgt, 'blastp', deps = dbfs+[srs[0]], verbose = True, 
                  args = [('-query',srs[0]),('-db',srs[1])], long_args = '-',
                  __kwargs_dict__ = kwargs )

