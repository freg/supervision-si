<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Stauts defines list stauts an activity or action can get in (lifecylce).
 */ 
require_once('_securityCheck.php');

class DocumentDirectory extends SqlElement {

  // extends SqlElement, so has $id
  public $_sec_Description;
  public $id;    // redefine $id to specify its visible place 
  public $name;
  public $idDocumentDirectory;
  public $location;
  public $idProject;
  public $idProduct;
  public $idResource;
  public $idUser;
  public $idDocumentType;
  //public $sortOrder=0;
  public $idle;
  //public $_sec_void;
  public $_sec_AccessRight;
  public $_DocumentRight;
  public $_accessRight_colSpan="2";
  
  
  public $_noCopy;
  
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%"># ${id}</th>
    <th field="location" width="45%">${location}</th>
    <th field="name" width="15%">${name}</th>
    <th field="nameProject" width="15%">${idProject}</th>
    <th field="nameProduct" width="15%">${idProduct}</th>
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';

   private static $_colCaptionTransposition = array('idDocumentDirectory' => 'parentDirectory',
                                                    'idDocumentType'=>'defaultType',
                                                    'idResource'=>'responsible'
                                                    );
   
   private static $_fieldsAttributes=array("name"=>"required",
                                           "location"=>"readonly",
                                           "idDocumentDirectory"=>"",
                                           'idUser'=>'hidden');  
   
   private static $_databaseColumnName = array();
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********
  
  /** ==========================================================================
   * Return the specific layout
   * @return String the layout
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  } 
  
  /** ========================================================================
   * Return the specific databaseColumnName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
  public function control() {
  	$result="";
    $pattern = '/^[a-zA-Z0-9][a-zA-Z0-9\-\_\ ]*\Z/';
    if (! preg_match($pattern, pq_nvl($this->name)) ) {
      $result.="<br/>" . i18n('invalidDirectoryName',null);
    }
    $crit="location='" . $this->location . "' and id<>" . Sql::fmtId($this->id);
    $dirList=$this->getSqlElementsFromCriteria(null, false, $crit);
    if (count($dirList)>0) {
      $result.="<br/>" . i18n('existingDirectoryName',null);
    }
    //gautier
    if ($this->idDocumentDirectory and $this->idDocumentDirectory==$this->id) {
      $result.="<br/>" . i18n('invalidDirectorySelf',null);
    }
    if ($this->id and $this->idDocumentDirectory
        and $this->idDocumentDirectory != $this->id) {
      $parentId = $this->idDocumentDirectory;
      $depth = 0;
      while ($parentId and $depth < 100) {
        if ($parentId == $this->id) {
          $result.="<br/>" . i18n('errorHierarchicLoop',null);
          break;
        }
        $parent = new DocumentDirectory($parentId);
        $parentId = $parent->idDocumentDirectory;
        $depth++;
      }
    }
    if($this->idDocumentDirectory != ""){
      $dir=new DocumentDirectory($this->idDocumentDirectory);
      $proj = new Project($dir->idProject);
      if($dir->idProject != ""){
        $subProjList= $proj->getSubProjectsList(false);
        $subProjList = array_flip($subProjList);
        array_push($subProjList, $dir->idProject);
        if(!in_array($this->idProject, $subProjList)){
          $result.="<br/>" . i18n('repertoryIsNotValid',null);
        }
      }
    }
    
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
    if ($result=="") {
      $result='OK';
    }
    
    return $result;    
  }
  
  public function delete () {
    $result=parent::delete();
    if (! pq_strpos($result,'id="lastOperationStatus" value="OK"')) {
      return $result;     
    }
    //delete directory if empty
    $dir=$this->getLocation();
    if (file_exists($dir)) {
    	if  (($files = @scandir($dir)) && count($files) <= 2) {
    	  rmdir($dir);
    	}
    }
    return $result;  
  }
  
  public function save() {
  	//$paramPathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
  	$paramPathSeparator="/"; // Save with Linux format (windows interprets it correctly)
  	$old=$this->getOld();
  	// #2373 - start
  	if (!$this->idDocumentDirectory and $this->location) {
  	  if ( pq_substr($this->location,(-1)*pq_strlen($this->name))==$this->name) {
  	    $search=pq_substr($this->location,0,pq_strlen($this->location)-pq_strlen($this->name)-1);
  	    $dir=SqlElement::getSingleSqlElementFromCriteria('DocumentDirectory',array('location'=>$search));
  	    if ($dir and $dir->id) {
  	      $this->idDocumentDirectory=$dir->id;
  	    }
  	  }
  	}
  	// #2373 - end
  	$this->location="";
  	if ($this->idDocumentDirectory) {
  		$dir=new DocumentDirectory($this->idDocumentDirectory);
  		$this->location=$dir->location;
  	}
  	
  	$this->location.=$paramPathSeparator . $this->name;
  	
  	$res='';
  	$status='';

  	$result=parent::save();
  	
  	if(RequestHandler::isCodeSet('lstDocRight') and RequestHandler::getValue('lstDocRight')!=""){
  	  $lstProf=pq_explode(',', RequestHandler::getValue('lstDocRight'));
  	  sort($lstProf);
  	  foreach ($lstProf as $id=>$idProf){
  	    if(RequestHandler::isCodeSet('documentRight_'.$idProf)){
  	      $documentRight=SqlElement::getSingleSqlElementFromCriteria("DocumentRight", array("idDocumentDirectory"=>$this->id,"idProfile"=>$idProf));
  	      $documentRight->idAccessMode=intval(RequestHandler::getValue('documentRight_'.$idProf));
  	      $res.=$documentRight->save();
  	
  	    }
  	  }
  	  if (pq_trim(pq_strpos($res, 'id="lastOperationStatus" value="OK"'))!=''){
  	    $status="OK";
  	  }
  	}
  	
    if (! pq_strpos($result,'id="lastOperationStatus" value="OK"') ) {
      if($status==''){
        return $result;
        
      }else {
        $result= i18n('messageDocumentsRightsSaved');
        $result.= '<input type="hidden" id="lastSaveId" value="'.$this->id.'">';
        $result.='<input type="hidden" id="lastOperation" value="update" />';
        $result.='<input type="hidden" id="lastOperationStatus" value="' . $status .'">';
      }
         
    }
    if (! $old->id) {
      $this->createDirectory();
    } else {
    	$newLocation=$this->getLocation();
    	$oldLocation=$old->getLocation();
    	if (! file_exists($oldLocation)) {
    		 $this->createDirectory();
    	} else {
    		$dir=new DocumentDirectory($this->idDocumentDirectory);
    		$dir->createDirectory();
        rename($oldLocation,$newLocation);    	
    	}
    } 
    //gautier 
    $tabIdSubdirectories = $this->getAllSubdirectories($this->id);
    $proj = new Project($this->idProject);
    $subProjList= $proj->getSubProjectsList(false);
    $subProjList = array_flip($subProjList);
    foreach ($tabIdSubdirectories as $id){
      $dir=new DocumentDirectory($id);
      if(in_array($dir->idProject, $subProjList) ){
        continue;
      }else{
        $dir->idProject = $this->idProject;
      }
      $dir->save();
    }

  	return $result;
  }
  
  function getAllSubdirectories($id) {
    $tabIdSubdirectories = array();
    $dir=new DocumentDirectory();
    $dirList=$dir->getSqlElementsFromCriteria(array('idDocumentDirectory'=>$id),false,null,'location asc');
    foreach ($dirList as $dir) {
      $tabIdSubdirectories[$dir->id] = $dir->id;
      $dir->getAllSubdirectories($dir->id);
    }
    return $tabIdSubdirectories;
  }
  
  function getSubdirectories(){
    if ($this->id===null or $this->id=='') {
    	return array();
    }
    $crit=array();
    $crit['idDocumentDirectory']=$this->id;
    $sorted=SqlList::getListWithCrit('DocumentDirectory',$crit,'name');
    return $sorted;
  }
  
  public function getRecursiveSubDirectoriesFlatList($includeSelf=false) {
  	$tab=$this->getSubdirectories();
  	$list=array();
  	if ($includeSelf) {
  		$list[$this->id]=$this->name;
  	}
  	if ($tab) {
  		foreach($tab as $id=>$name) {
  			$list[$id]=$name;
  			$subobj=new DocumentDirectory();
  			$subobj->id=$id;
  			$sublist=$subobj->getRecursiveSubDirectoriesFlatList();
  			if ($sublist) {
  				$list=array_merge_preserve_keys($list,$sublist);
  			}
  		}
  	}
  	return $list;
  }
  
  
  function createDirectory() {
  	$paramPathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
  	$split=pq_explode($paramPathSeparator,$this->getLocation());
  	$rep="";
  	foreach ($split as $sp) {
  	  $rep.= $sp . $paramPathSeparator;
  		if (! file_exists($rep)) {
  			mkdir($rep,0777,true);
  		}	
  	}
  	
  }
  
  public function getLocation() {
  	$paramPathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
  	$root=Parameter::getGlobalParameter('documentRoot');
  	if (! $root) { // Document Root not set
  		errorLog("ERROR in DocumentDirectory::getLocation() : parameter 'paramPathSeparator' is not set");
  		echo "<span class='messageERROR'>Some parameter is not correctly set. Check for error in log file.</span>";
  		exit;
  	}
  	if (pq_substr($root,-1,1)!=$paramPathSeparator) {
  		$root.=$paramPathSeparator;
  	}
  	return $root . $this->location ;
  }
  
  // ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    if ($colName=="name"){
      $colScript .= '<script type="dojo/connect" event="onKeyPress" >';
      $colScript .= '  dijit.byId("location").set("value","...");';
      $colScript .= '  formChanged();';      
      $colScript .= '</script>';     
    } else if ($colName=="idDocumentDirectory") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  dijit.byId("location").set("value","...");';
      $colScript .= '  formChanged();';      
      $colScript .= '</script>';      
    } 
    return $colScript;
  }
  
  public function setAttributes(){
    if(! $this->id){
//       self::$_fieldsAttributes ['_DocumentRight'] = 'hidden';
//       self::$_fieldsAttributes ['_sec_AccessRight'] = 'hidden';
    }else {
      $dR=new DocumentRight();
      $classDR=get_class($dR);
      $menu=SqlElement::getSingleSqlElementFromCriteria('Menu', array('name'=>'menu'.$classDR));
      $rightUpdate=securityGetAccessRightYesNo($menu->name,'update',$dR);
      $rightRead=securityGetAccessRightYesNo($menu->name,'read',$dR);
      if ( !securityCheckDisplayMenu(null, $classDR) or $rightRead!="YES") {
        self::$_fieldsAttributes ['_sec_AccessRight'] = 'hidden';
        self::$_fieldsAttributes ['_sec_AccessRight'] = 'hidden';
      }
    }
  }
  
  private static $arrayCanSee=array();
  public static function canSeeDirectory($idDirectory, $idProject,  $mode='read', $user=null) {
    if (!$user) $user=getSessionUser();
    $prf=$user->getProfile($idProject);
    if (!isset(self::$arrayCanSee[$mode])) self::$arrayCanSee[$mode]=array();
    if (!isset(self::$arrayCanSee[$mode][$prf])) self::$arrayCanSee[$mode][$prf]=array();
    if (isset(self::$arrayCanSee[$mode][$prf][$idDirectory])) return self::$arrayCanSee[$mode][$prf][$idDirectory];
    $dr=SqlElement::getSingleSqlElementFromCriteria('DocumentRight', array('idDocumentDirectory'=>$idDirectory,'idProfile'=>$prf));
    if (!$dr or !$dr->id) {
      $right=true;
    } else {
      $right=false;
      $ap=new AccessProfile($dr->idAccessMode);
      $col='idAccessScope'.pq_ucfirst($mode);
      $as=new AccessScope($ap->$col);
      $code=$as->accessCode;
      if ($code=='NO') $right=false;
      else if ($code=='OWN') $right=true;
      else if ($code=='ALL') $right=true;
      else if ($code=='RES') $right=true;
      else if ($code=='PRO') {
        $pList=$user->getVisibleProjects();
        if (!$idProject or isset($pList[$idProject])) $right=true;
      }
    }
    self::$arrayCanSee[$mode][$prf][$idDirectory]=$right;
    return $right;
  }
}
?>