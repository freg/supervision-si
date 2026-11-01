<?php
/*
 *	@author: qCazelles 
 */

require_once('_securityCheck.php');
class WorkUnit extends SqlElement {
	
	public $id;   
	public $reference;
	public $name;
	public $description;
	public $entering;
	public $deliverable;
	public $validityDate;
    public $idCatalogUO;
    public $idProject;
    public $idle;
  	
	private static $_databaseCriteria = array();
	private static $_databaseColumnName = array(
	    'name'   => 'reference'
	);
	/** ==========================================================================
	 * Constructor
	 * @param $id Int the id of the object in the database (null if not stored yet)
	 * @return void
	 */

	
	/** ========================================================================
	 * Return the specific database criteria
	 * @return String the databaseTableName
	 */
	protected function getStaticDatabaseCriteria() {
	  return self::$_databaseCriteria;
	}
	
	/** ==========================================================================
	 * Construct
	 * @return void
	 */
	function __construct($id = NULL, $withoutDependentObjects=false) {
		parent::__construct($id,$withoutDependentObjects);
	}
	
	public function save() { 
	  $this->name = $this->reference;
	  if (!$this->idProject) {
	    $cata=new CatalogUO($this->idCatalogUO);
	    $this->idProject=$cata->idProject;
	  }
	  $result = parent::save();
	  return $result;
	}	
	
	public function deleteControl()
	{
	  $result="";
	  $actPl = new ActivityWorkUnit();
	  $isUsed = $actPl->countSqlElementsFromCriteria(array('idWorkUnit'=>$this->id));
	  if ($isUsed){
	    $result .= '<br/>' . i18n ( 'workUnitIsUseByActivity' );
	  }
	  if (! $result) {
	    $result=parent::deleteControl();
	  }
	  return $result;
	}
	/** ==========================================================================
	 * Destructor
	 * @return void
	 */
	function __destruct() {
		parent::__destruct();
	}
	/**
	 * ========================================================================
	 * Return the specific databaseColumnName
	 *
	 * @return String the databaseTableName
	 */
	protected function getStaticDatabaseColumnName() {
	  return self::$_databaseColumnName;
	}
	
	
}